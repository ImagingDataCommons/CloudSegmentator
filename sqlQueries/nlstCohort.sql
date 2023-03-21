#standardSQL

-- The point of this query is to remove the CT Image Series from nlst study which do not conform to
-- geometrical checks generally required for NIFTI file converison

-- The assumptions made here are
  -- consider only those series that have CT modality and belong to the NLST collection

  -- do not contain LOCALIZER in ImageType

  -- all instances have identical values for ImageOrientationPatient (converted to string for the purposes of comparison)
  -- have number of instances in the series equal to the number of distinct values of ImagePositionPatient attribute
  -- (converted to string for the purposes of comparison)

  -- all instances have identical values of PixelSpacing (converted to string for the purposes of comparison)

  -- all instances have identical values of SliceThickness

  -- with sliceIntervalDifference defined as the difference between the values of the 3rd component of ImagePositionPatient,
  -- after sorting all instances by that third component, having the difference between the largest and smallest 
  --values of sliceIntervalDifference less than 0.01

WITH
  -- Create a common table expression (CTE) named nonLocalizerRawData
  nonlocalizerrawdata AS (
  SELECT
    seriesinstanceuid,
    sopinstanceuid,
    slicethickness,
    -- Cast Exposure column as FLOAT64 data type 
    safe_cast(exposure AS float64) exposure,
    -- Cast unnested Image Patient Position column as FLOAT64 data type and rename it as zImagePosition as we filter for z-axis
    safe_cast(ipp AS float64) AS zimageposition,
    -- Calculate the difference between the current and next zImagePosition for each SeriesInstanceUID for slice_interval
    lead (safe_cast(ipp AS float64)) over (partition BY seriesinstanceuid ORDER BY safe_cast(ipp AS float64)) -safe_cast(ipp AS float64) AS slice_interval,
    -- Convert ImageOrientationPatient array to string separated by "/" 
    array_to_string(imageorientationpatient, "/") iop,
    -- Convert PixelSpacing array to string separated by "/" 
    array_to_string(pixelspacing, "/") pixelspacing,
    gcs_url sopinstanceurl,
    instance_size instancesize,
    -- Concatenate viewer URL with StudyInstanceUID and SeriesInstanceUID parameters 
    concat("https://viewer.imaging.datacommons.cancer.gov/viewer/",studyinstanceuid,"?seriesInstanceUID=",seriesinstanceuid) AS viewerurl,
  FROM
     `bigquery-public-data.idc_current.dicom_all` bid
  LEFT JOIN
     unnest(bid.imagepositionpatient) ipp
  WITH offset
  --Using offset creates a column and with the index of the elements(starting from 1) in the array in order
     AS axes
  WHERE
     collection_id = "nlst" AND modality = "CT" AND axes=2 AND "LOCALIZER" NOT IN unnest(imagetype)
 ),
geometrychecks AS (
  SELECT
    seriesinstanceuid,
    -- Aggregate distinct slice_interval values into an array 
    array_agg(DISTINCT(slice_interval) IGNORE nulls) AS sliceintervaldifferences,
    -- Aggregate distinct Exposure values into an array 
    array_agg(DISTINCT(exposure) IGNORE nulls) AS distinctexposures,
    -- Count the number of distinct Image Orientation Patient values 
    count(DISTINCT iop) iopcount,
    -- Count the number of distinct pixelSpacing values 
    count(DISTINCT pixelspacing) pixelspacingcount,
    -- Count the number of distinct zImagePosition values 
    count(DISTINCT zimageposition) positioncount,
     -- Count the number of distinct SOPInstanceUIDs 
     count(DISTINCT sopinstanceuid) sopinstancecount,
     -- Count the number of distinct SliceThickness values 
     count(DISTINCT slicethickness) slicethicknesscount,
     -- Count the number of distinct Exposure values 
     count(DISTINCT exposure) exposurecount,
     viewerurl,
     -- Calculate sum of instanceSize divided by 1024*1024 to get te size in MB
     sum(instancesize)/1024/1024 seriessizeinmb,
      -- Concatenate "cp ", replace "gs://" with "s3://" in sopInstanceUrl to make the urls work with s5cmd,
      -- add " idc_data/" which acts as destination folder for s5cmd and
      -- at end for each row separated by new line character "\n" so it will be
      -- ready for creating a manifest file later in the workflow
      string_agg (concat("cp ",REPLACE(sopinstanceurl, "gs://", "s3://"), " idc_data/"), "\n") AS s5cmdurls
  FROM
      nonlocalizerrawdata
  GROUP BY
      seriesinstanceuid, viewerurl
  HAVING
    iopcount=1 --we expect only one image orientation in a series
    AND pixelspacingcount=1  --we expect identical pixel spacing in a series
    AND sopinstancecount=positioncount --we expect position counts are same as sopInstances count. this would also allow us to filter 4D series
    AND slicethicknesscount=1 --we expect identical slice thickness in a series
    --AND exposureCount=1

)
#finally displaying the attributes that we would be interested
SELECT
  seriesinstanceuid,
  iopcount,
  pixelspacingcount,
  positioncount,
  sopinstancecount,
  slicethicknesscount,
  max(sid) AS maxsliceintervaldifference,
  min(sid) AS minsliceintervaldifference,
  max(sid) -min (sid) AS sliceintervalifferencetolerance,
  exposurecount,
  max(de) AS maxexposure,
  min(de) AS minexposure,
  max(de) -min (de) AS maxexposuredifference,
  seriessizeinmb,
  --viewerUrl,
  s5cmdurls
FROM
  geometrychecks
LEFT JOIN
  unnest(sliceintervaldifferences) sid
LEFT JOIN
  unnest(distinctexposures) de

GROUP BY
  seriesinstanceuid,
  iopcount,
  pixelspacingcount,
  positioncount,
  sopinstancecount,
  slicethicknesscount,
  exposurecount,
  seriessizeinmb,
  --viewerUrl,
  s5cmdurls

HAVING sliceintervalifferencetolerance<0.01
ORDER BY
sliceintervalifferencetolerance DESC,
maxexposuredifference DESC,
seriesinstanceuid

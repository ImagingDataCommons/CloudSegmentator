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
  nonLocalizerRawData AS (
  SELECT
    SeriesInstanceUID,
    SOPInstanceUID,
    SliceThickness,
    -- Cast Exposure column as FLOAT64 data type 
    SAFE_CAST(Exposure AS FLOAT64) Exposure,
    -- Cast unnested Image Patient Position column as FLOAT64 data type and rename it as zImagePosition as we filter for z-axis
    SAFE_CAST(ipp AS FLOAT64) AS zImagePosition,
    -- Calculate the difference between the current and next zImagePosition for each SeriesInstanceUID for slice_interval
    lead (SAFE_CAST(ipp AS FLOAT64)) OVER (PARTITION BY SeriesInstanceUID ORDER BY SAFE_CAST(ipp AS FLOAT64)) -SAFE_CAST(ipp AS FLOAT64) AS slice_interval,
    -- Convert ImageOrientationPatient array to string separated by "/" 
    ARRAY_TO_STRING(ImageOrientationPatient, "/") iop,
    -- Convert PixelSpacing array to string separated by "/" 
    ARRAY_TO_STRING(PixelSpacing, "/") pixelSpacing,
    gcs_url sopInstanceUrl,
    instance_size instanceSize,
    -- Concatenate viewer URL with StudyInstanceUID and SeriesInstanceUID parameters 
    CONCAT("https://viewer.imaging.datacommons.cancer.gov/viewer/",StudyInstanceUID,"?seriesInstanceUID=",SeriesInstanceUID) AS viewerUrl,
  FROM
     `bigquery-public-data.idc_current.dicom_all` bid
  LEFT JOIN
     UNNEST(bid.ImagePositionPatient) ipp
  WITH OFFSET
  --Using offset creates a column and with the index of the elements(starting from 1) in the array in order
     AS axes
  WHERE
     collection_id = "nlst" AND Modality = "CT" AND axes=2 AND "LOCALIZER" NOT IN UNNEST(ImageType)
 ),
geometryChecks AS (
  SELECT
    SeriesInstanceUID,
    -- Aggregate distinct slice_interval values into an array 
    ARRAY_AGG(DISTINCT(slice_interval) ignore nulls) AS sliceIntervalDifferences,
    -- Aggregate distinct Exposure values into an array 
    ARRAY_AGG(DISTINCT(Exposure) ignore nulls) AS distinctExposures,
    -- Count the number of distinct Image Orientation Patient values 
    COUNT(DISTINCT iop) iopCount,
    -- Count the number of distinct pixelSpacing values 
    COUNT(DISTINCT pixelSpacing) pixelSpacingCount,
    -- Count the number of distinct zImagePosition values 
    COUNT(Distinct zImagePosition) positionCount,
     -- Count the number of distinct SOPInstanceUIDs 
     COUNT(Distinct SOPInstanceUID) sopInstanceCount,
     -- Count the number of distinct SliceThickness values 
     COUNT(Distinct SliceThickness) sliceThicknessCount,
     -- Count the number of distinct Exposure values 
     COUNT(Distinct Exposure) exposureCount,
     viewerUrl,
     -- Calculate sum of instanceSize divided by 1024*1024 to get te size in MB
     sum(instanceSize)/1024/1024 seriesSizeInMB,
      -- Concatenate "cp ", replace "gs://" with "s3://" in sopInstanceUrl to make the urls work with s5cmd,
      -- add " idc_data/" which acts as destination folder for s5cmd and
      -- at end for each row separated by new line character "\n" so it will be
      -- ready for creating a manifest file later in the workflow
      string_agg (CONCAT("cp ",REPLACE(sopInstanceUrl, "gs://", "s3://"), " idc_data/"), "\n") as s5cmdUrls
  FROM
      nonLocalizerRawData
  GROUP BY
      SeriesInstanceUID, viewerUrl
  HAVING
    iopCount=1 --we expect only one image orientation in a series
    AND pixelSpacingCount=1  --we expect identical pixel spacing in a series
    AND sopInstanceCount=positionCount --we expect position counts are same as sopInstances count. this would also allow us to filter 4D series
    AND sliceThicknessCount=1 --we expect identical slice thickness in a series
    --AND exposureCount=1

)
#finally displaying the attributes that we would be interested
SELECT
  SeriesInstanceUID,
  iopCount,
  pixelSpacingCount,
  positionCount,
  sopInstanceCount,
  sliceThicknessCount,
  max(sid) as maxSliceIntervalDifference,
  min(sid) as minSliceIntervalDifference,
  max(sid) -min (sid) as sliceIntervalifferenceTolerance,
  exposureCount,
  max(de) as maxExposure,
  min(de) as minExposure,
  max(de) -min (de) as maxExposureDifference,
  seriesSizeInMB,
  --viewerUrl,
  s5cmdUrls
FROM
  geometryChecks
LEFT JOIN
  UNNEST(sliceIntervalDifferences) sid
LEFT JOIN
  UNNEST(distinctExposures) de

GROUP BY
  SeriesInstanceUID,
  iopCount,
  pixelSpacingCount,
  positionCount,
  sopInstanceCount,
  sliceThicknessCount,
  exposureCount,
  seriesSizeInMB,
  --viewerUrl,
  s5cmdUrls

HAVING sliceIntervalifferenceTolerance<0.01
ORDER BY
sliceIntervalifferenceTolerance desc,
maxExposureDifference desc,
SeriesInstanceUID

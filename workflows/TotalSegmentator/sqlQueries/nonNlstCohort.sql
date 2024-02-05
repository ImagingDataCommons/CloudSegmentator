#standardSQL

-- The point of this query is to remove the CT Image Series from nlst study which do not conform to
-- geometrical checks generally required for NIFTI file converison
-- also to remove those series that require additional decompression steps before passing to dcm2niix for conversion to NIfTI format.

-- The assumptions made here are
  -- consider only those series that have CT modality and belong to the NLST collection and TransferSyntaxUID's NOT IN ( '1.2.840.10008.1.2.4.70','1.2.840.10008.1.2.4.51')
  -- do not contain LOCALIZER in ImageType
  -- all instances in a series have identical values for ImageOrientationPatient (converted to string for the purposes of comparison)
  -- all instances in a series have 1 ± 0.01 as the dot product between cross product of first and second vectors, and [1,0,0] in ImageOrientationPosition
  -- have number of instances in the series equal to the number of distinct values of ImagePositionPatient attribute
      -- (converted to string for the purposes of comparison)
  -- all instances in a series have identical values for the first two components of ImagePositionPatient
  -- all instances in a series have identical values of PixelSpacing (converted to string for the purposes of comparison)
  -- all instances in a series have identical values of SliceThickness--this requirement has been relaxed now
  -- all instances in a series have identical pixel Rows and similarly identical pixel Columns
  -- with sliceIntervalDifference defined as the difference between the values of the 3rd component of ImagePositionPatient,
  -- after sorting all instances by that third component, having the difference between the largest and smallest 
  --values of sliceIntervalDifference less than 0.01
  
  WITH
  -- Create a common table expression (CTE) named localizerAndJpegCompressedSeries
  localizerAndJpegCompressedSeries AS (
  Select SeriesInstanceUID  from 
  `bigquery-public-data.idc_v17.dicom_all` bid, bid.ImageType image_type 
   where 
   image_type='LOCALIZER' OR  
   TransferSyntaxUID  IN ( '1.2.840.10008.1.2.4.70','1.2.840.10008.1.2.4.51')
   --these are the classes that require additional processing before converting DICOM files to NIfTI using dcm2niix
  ),
  -- Create a common table expression (CTE) named nonLocalizerRawData 
  nonLocalizerRawData AS (
    SELECT
      SeriesInstanceUID,
      StudyInstanceUID,
      PatientID,
      SOPInstanceUID,
      SliceThickness,
      ImageType,
      TransferSyntaxUID,
      SeriesNumber,
      aws_bucket,
      crdc_series_uuid,

      -- Cast Exposure column as FLOAT64 data type
      SAFE_CAST(Exposure AS FLOAT64) Exposure,
      -- Cast unnested Image Patient Position column as FLOAT64 data type and rename it as zImagePosition as we filter for the z-axis
      SAFE_CAST(ipp AS FLOAT64) AS zImagePosition,
      -- first and second coordinates 
      CONCAT(ipp2, '/', ipp3) AS xyImagePosition,
      -- Calculate the difference between the current and next zImagePosition for each SeriesInstanceUID for slice_interval
      LEAD(SAFE_CAST(ipp AS FLOAT64)) OVER (PARTITION BY SeriesInstanceUID ORDER BY SAFE_CAST(ipp AS FLOAT64)) - SAFE_CAST(ipp AS FLOAT64) AS slice_interval,
      -- Convert ImageOrientationPatient array to a string separated by "/"
      ARRAY_TO_STRING(ImageOrientationPatient, '/') AS iop,
      (
        -- Extract the first three elements of ImageOrientationPatient array and convert them to FLOAT64 data type
        SELECT ARRAY_AGG(SAFE_CAST(part AS FLOAT64))
        FROM UNNEST(ImageOrientationPatient) part WITH OFFSET index
        WHERE index BETWEEN 0 AND 2
      ) AS x_vector,
      (
        -- Extract the last three elements of ImageOrientationPatient array and convert them to FLOAT64 data type
        SELECT ARRAY_AGG(SAFE_CAST(part AS FLOAT64))
        FROM UNNEST(ImageOrientationPatient) part WITH OFFSET index
        WHERE index BETWEEN 3 AND 5
      ) AS y_vector,
      -- Convert PixelSpacing array to a string separated by "/"
      ARRAY_TO_STRING(PixelSpacing, '/') AS pixelSpacing,
      -- Store the number of rows and columns in the pixel matrix
      `Rows` AS pixelRows,
      `Columns` AS pixelColumns,
      -- Store the size of the SOP Instance in bytes
      instance_size AS instanceSize,
    FROM
      `bigquery-public-data.idc_v17.dicom_all` bid
    LEFT JOIN
      UNNEST(bid.ImagePositionPatient) ipp WITH OFFSET AS axes
    LEFT JOIN
      UNNEST(bid.ImagePositionPatient) ipp2 WITH OFFSET AS axis1
    LEFT JOIN
      UNNEST(bid.ImagePositionPatient) ipp3 WITH OFFSET AS axis2
    WHERE
      -- Filter for CT images in the NLST collection that are not localizers 
      --and removing the transfer syntax ids that require additional processing (decompression before passing to dcm2niix)
      collection_id != 'nlst' AND Modality = 'CT' AND axes = 2 AND axis1 = 0 AND axis2 = 1 
      AND SeriesInstanceUID not in (Select SeriesInstanceuID from  localizerAndJpegCompressedSeries)
  )
,
crossProduct AS (
  SELECT
    SOPInstanceUID,
    SeriesInstanceUID,
    -- Calculate the cross product of x_vector and y_vector for each row in nonLocalizerRawData
    (SELECT AS STRUCT
      (x_vector[OFFSET(1)]*y_vector[OFFSET(2)] - x_vector[OFFSET(2)]*y_vector[OFFSET(1)]) AS x,
      (x_vector[OFFSET(2)]*y_vector[OFFSET(0)] - x_vector[OFFSET(0)]*y_vector[OFFSET(2)]) AS y,
      (x_vector[OFFSET(0)]*y_vector[OFFSET(1)] - x_vector[OFFSET(1)]*y_vector[OFFSET(0)]) AS z
    ) AS xyCrossProduct
  FROM nonLocalizerRawData
),
dotProduct AS (
  SELECT
    SOPInstanceUID,
    SeriesInstanceUID,
    xyCrossProduct,
    -- Calculate the dot product of xyCrossProduct and [0,0,1] for each row in crossProduct
    (
      SELECT SUM(element1 * element2)
      FROM UNNEST([xyCrossProduct.x, xyCrossProduct.y, xyCrossProduct.z]) element1 WITH OFFSET pos
      JOIN UNNEST([0,0,1]) element2 WITH OFFSET pos
      USING(pos)
    ) AS xyDotProduct
  FROM crossProduct
)
,
geometryChecks AS (
  SELECT
    SeriesInstanceUID,
    seriesNumber,
    aws_bucket,
    crdc_series_uuid,
    StudyInstanceUID,
    PatientID,
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
    -- Count the number of distinct xyImagePosition values     
    COUNT(Distinct xyImagePosition) xyPositionCount,
     -- Count the number of distinct SOPInstanceUIDs 
     COUNT(Distinct SOPInstanceUID) sopInstanceCount,
     -- Count the number of distinct SliceThickness values 
     COUNT(Distinct SliceThickness) sliceThicknessCount,
     -- Count the number of distinct Exposure values 
     COUNT(Distinct Exposure) exposureCount,
     -- Count the number of distinct pixel row values 
     COUNT(Distinct pixelRows) pixelRowCount,
     -- Count the number of distinct pixel column values      
     COUNT(Distinct pixelColumns) pixelColumnCount,
     --Determining maximum dotProduct..ideally this should be zero
     max(xyDotProduct) dotProduct,
     #viewerUrl,
     -- Calculate sum of instanceSize divided by 1024*1024 to get te size in MB
     sum(instanceSize)/1024/1024 seriesSizeInMiB,
  FROM
      nonLocalizerRawData
  JOIN dotProduct using (SeriesInstanceUID, SOPInstanceUID)
  GROUP BY
      SeriesInstanceUID, 
      seriesNumber,
      aws_bucket,
      crdc_series_uuid,
      StudyInstanceUID,
      PatientID
  HAVING
    iopCount=1 --we expect only one image orientation in a series
    AND pixelSpacingCount=1  --we expect identical pixel spacing in a series
    AND sopInstanceCount=positionCount --we expect position counts are same as sopInstances count. this would also allow us to filter 4D series
    AND xyPositionCount =1 --we expect first two values are same across the series
    --AND sliceThicknessCount=1 --we expect identical slice thickness in a series, but this requirement is relaxed upon Dr. David Clunie's advice
    AND pixelColumnCount = 1 --we expect consistent pixel Columns across the series
    AND pixelRowCount = 1 --we expect consistent pixel Rows across the series
    AND abs(dotProduct) between 0.99 and 1.01 --we expect the dot product of x and y vectors to be ideally one, however we are allowing for minor deviations (0.01)

    --AND exposureCount=1

)

SELECT
  SeriesInstanceUID,
  seriesNumber,
  StudyInstanceUID,
  PatientID,
  iopCount,
  dotProduct,
  pixelSpacingCount,
  positionCount,
  sopInstanceCount,
  xyPositionCount,
  sliceThicknessCount,
  pixelRowCount,
  pixelColumnCount,
  max(sid) as maxSliceIntervalDifference,
  min(sid) as minSliceIntervalDifference,
  max(sid) -min (sid) as sliceIntervalifferenceTolerance,
  exposureCount,
  max(de) as maxExposure,
  min(de) as minExposure,
  max(de) -min (de) as maxExposureDifference,
  seriesSizeInMiB,
  CONCAT("cp --show-progress s3://",aws_bucket,"/",crdc_series_uuid,"/* idc_data/") AS s5cmdUrls,
  CONCAT('https://viewer.imaging.datacommons.cancer.gov/viewer/', StudyInstanceUID, '?seriesInstanceUID=', SeriesInstanceUID) viewerUrl,

FROM
  geometryChecks
LEFT JOIN
  UNNEST(sliceIntervalDifferences) sid
LEFT JOIN
  UNNEST(distinctExposures) de

GROUP BY
  SeriesInstanceUID,
  seriesNumber,
  StudyInstanceUID,
  PatientID,
  iopCount,
  dotProduct,
  pixelSpacingCount,
  positionCount,
  sopInstanceCount,
  xyPositionCount,
  sliceThicknessCount,
  pixelRowCount,
  pixelColumnCount,
  exposureCount,
  seriesSizeInMiB,
  viewerUrl,
  s5cmdUrls

#Setting the minimum number of Series to be 50
HAVING sliceIntervalifferenceTolerance<0.01 and sopInstanceCount >=50 
ORDER BY
sliceIntervalifferenceTolerance desc,
maxExposureDifference desc,
SeriesInstanceUID
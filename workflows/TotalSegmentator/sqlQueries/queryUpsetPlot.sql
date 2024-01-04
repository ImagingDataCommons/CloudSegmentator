WITH
  -- Create a common table expression (CTE) named nonLocalizerRawData
  nonLocalizerRawData AS (
    SELECT
      SeriesInstanceUID,
      StudyInstanceUID,
      PatientID,
      SOPInstanceUID,
      SliceThickness,
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
      -- Store the GCS URL of the SOP Instance
      gcs_url AS sopInstanceUrl,
      -- Store the size of the SOP Instance in bytes
      instance_size AS instanceSize,
      -- Concatenate viewer URL with StudyInstanceUID and SeriesInstanceUID parameters to create a link for viewing the series
      CONCAT('https://viewer.imaging.datacommons.cancer.gov/viewer/', StudyInstanceUID, '?seriesInstanceUID=', SeriesInstanceUID) AS viewerUrl
    FROM
      `bigquery-public-data.idc_current.dicom_all` bid
    LEFT JOIN
      UNNEST(bid.ImagePositionPatient) ipp WITH OFFSET AS axes
    LEFT JOIN
      UNNEST(bid.ImagePositionPatient) ipp2 WITH OFFSET AS axis1
    LEFT JOIN
      UNNEST(bid.ImagePositionPatient) ipp3 WITH OFFSET AS axis2
    WHERE
      -- Filter for CT images in the NLST collection that are not localizers 
      --and removing the transfer syntax ids that require additional processing (decompression before passing to dcm2niix)
      collection_id = 'nlst' AND Modality = 'CT' AND axes = 2 AND axis1 = 0 AND axis2 = 1 AND 'LOCALIZER' NOT IN UNNEST(ImageType) AND TransferSyntaxUID NOT IN ( '1.2.840.10008.1.2.4.70','1.2.840.10008.1.2.4.51')
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
  JOIN dotProduct using (SeriesInstanceUID, SOPInstanceUID)
  GROUP BY
      SeriesInstanceUID, 
      StudyInstanceUID,
      PatientID,
      viewerUrl
  -- HAVING
  --   iopCount=1 --we expect only one image orientation in a series
  --   AND pixelSpacingCount=1  --we expect identical pixel spacing in a series
  --   AND sopInstanceCount=positionCount --we expect position counts are same as sopInstances count. this would also allow us to filter 4D series
  --   AND xyPositionCount =1 --we expect first two values are same across the series
  --   --AND sliceThicknessCount=1 --we expect identical slice thickness in a series, but this requirement is relaxed upon Dr. David Clunie's advice
  --   AND pixelColumnCount = 1 --we expect consistent pixel Columns across the series
  --   AND pixelRowCount = 1 --we expect consistent pixel Rows across the series
  --   AND abs(dotProduct) between 0.99 and 1.01 --we expect the dot product of x and y vectors to be ideally one, however we are allowing for minor deviations (0.01)

  --   --AND exposureCount=1

)
#finally displaying the attributes that we would be interested
SELECT
  SeriesInstanceUID,
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
  seriesSizeInMB,
 -- viewerUrl,
 -- s5cmdUrls
FROM
  geometryChecks
LEFT JOIN
  UNNEST(sliceIntervalDifferences) sid
LEFT JOIN
  UNNEST(distinctExposures) de

GROUP BY
  SeriesInstanceUID,
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
  seriesSizeInMB
--  viewerUrl,
--  s5cmdUrls
-- #Setting the minimum number of Series to be 50
-- HAVING sliceIntervalifferenceTolerance<0.01 and sopInstanceCount >=50
ORDER BY
sliceIntervalifferenceTolerance desc,
maxExposureDifference desc,
SeriesInstanceUID

WITH
  nonLocalizerRawData AS (
  SELECT
    SeriesInstanceUID,
    SOPInstanceUID,
    SliceThickness,
    SAFE_CAST(Exposure AS FLOAT64) Exposure,
    SAFE_CAST(ipp AS FLOAT64) AS zImagePosition,
    --lead (SAFE_CAST(ipp AS FLOAT64)) OVER (PARTITION BY SeriesInstanceUID ORDER BY SAFE_CAST(ipp AS FLOAT64)) nextZImagePosition,
    lead (SAFE_CAST(ipp AS FLOAT64)) OVER (PARTITION BY SeriesInstanceUID ORDER BY SAFE_CAST(ipp AS FLOAT64)) -SAFE_CAST(ipp AS FLOAT64) AS slice_interval,
    ARRAY_TO_STRING(ImageOrientationPatient, "/") iop,
    ARRAY_TO_STRING(PixelSpacing, "/") pixelSpacing,
    gcs_url sopInstanceUrl,
    instance_size instanceSize,
    CONCAT("https://viewer.imaging.datacommons.cancer.gov/viewer/",StudyInstanceUID,"?seriesInstanceUID=",SeriesInstanceUID) AS viewerUrl,
  FROM
    `bigquery-public-data.idc_current.dicom_all` bid
  LEFT JOIN
    UNNEST(bid.ImagePositionPatient) ipp
  WITH
  OFFSET
    AS axes
  WHERE
    collection_id = "nlst"
    AND Modality = "CT"
    AND axes=2
    AND "LOCALIZER" NOT IN UNNEST(ImageType)
 ),
  geometryChecks AS (
  SELECT
    SeriesInstanceUID,
    ARRAY_AGG(DISTINCT(slice_interval) ignore nulls) AS sliceIntervalDifferences,
    ARRAY_AGG(DISTINCT(Exposure) ignore nulls) AS distinctExposures,
    COUNT(DISTINCT iop) iopCount,
    COUNT(DISTINCT pixelSpacing) pixelSpacingCount,
    COUNT(Distinct zImagePosition) positionCount,
    COUNT(Distinct SOPInstanceUID) sopInstanceCount,
    COUNT(Distinct SliceThickness) sliceThicknessCount,
    COUNT(Distinct Exposure) exposureCount,
    viewerUrl,
    sum(instanceSize)/1000000 seriesSizeInMB,
    string_agg (CONCAT("cp ",REPLACE(sopInstanceUrl, "gs://", "s3://"), " idc_data/"), "\n") as s5cmdUrls 
  FROM
    nonLocalizerRawData
  GROUP BY
    SeriesInstanceUID,
    viewerUrl
  HAVING
    iopCount=1
    AND pixelSpacingCount=1
    AND sopInstanceCount=positionCount
    AND sliceThicknessCount=1
    --AND exposureCount=1

)
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

# The notebooks mentioned on this page serve various purposes in different stages of data processing, from preprocessing to postprocessing. 

# Here’s a brief overview:

# Preprocessing
- Applies the sql query to filter out series with <50 slices and geometrically inconsistent series
- Data is dividied into batches of 12 series
- SeriesInstanceUIDs are passed
    - as Manifests are created for use on SB-CGC
    - as list in the data table for use on Terra


# Notebooks used for oneVM, twoVM, and threeVM

## oneVM: 
- endToEndTotalSegmentator

## twoVM: 
- downloadDicomAndConvertAndInferenceTotalSegmentatorNotebook
- dicomsegAndRadiomicsSR_Notebook

## threeVM: 
- downloadDicomAndConvertNotebook
- inferenceTotalSegmentatorNotebook
- dicomsegAndRadiomicsSR_Notebook

# PostprocessingTerra
- Levarages the URLs (populated by Terra automatically) to the compressed DICOM SEG and SR files
- Decompresses the DICOM SEG and SR files and push to GCP storage bucket

# preProccessing_of_postProcessingExtractPerframe
- Exporting metadata from GCP Healthcare DICOM stores have a limit of 1 MB [^1 ]and drops store the PerFrameFunctionalGroupsSequence DICOM attribute
- Prepares the Terra datatable by assining 10 batches of compressed DICOM SEG files generated in the earlier step. Essentially 10*12=120 DICOM SEG files per batch 

# postProcessingExtractPerframe
- Decompresses the DICOM SEG files 
- For each SEG, parses the PerFrameFunctionalGroupsSequence attribute
- creates a compressed CSV

# uploadPerFrameToBigquery.ipynb
- Decompresses every CSV with PerFrameFunctionalGroupsSequence and uploads it to bigquery
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import UID

import sys

# open the file passed as first argument using pydicom
ds_src = pydicom.dcmread(sys.argv[1])

#print("Initial length: "+str(get_sq_size(ds.PerFrameFunctionalGroupsSequence)))

print("Loaded input file")
per_group_segments = []

for group in range(4):
  # Create some temporary filenames
  filename = "group_"+str(group)+".dcm"

  # Populate required values for file meta information
  file_meta = FileMetaDataset()
  file_meta.MediaStorageSOPClassUID = UID('1.2.840.10008.5.1.4.1.1.2')
  file_meta.MediaStorageSOPInstanceUID = UID("1.2.3")
  file_meta.ImplementationClassUID = UID("1.2.3.4")

  # Create the FileDataset instance (initially no data elements, but file_meta
  # supplied)
  ds = FileDataset(filename, {},
                 file_meta=file_meta, preamble=b"\0" * 128)
  # create a new pydicom dataset
  per_group_segments.append(ds)
  per_group_segments[-1].PerFrameFunctionalGroupsSequence = pydicom.Sequence()

# iterate over the items in the per-frame functional groups sequence
for i, item in enumerate(ds_src.PerFrameFunctionalGroupsSequence):
  # get referenced segment number from the frame content sequence
  segment_number = item.SegmentIdentificationSequence[0].ReferencedSegmentNumber

  # if the segment number matches the current group, append the item to the new dataset
  per_group_segments[segment_number % 4].PerFrameFunctionalGroupsSequence.append(item)

for group in range(4):
  # calculate the size in bytes of the PerFRameFunctionalGroupsSequence for the current group
  #print("Group "+str(group)+" length: "+str(get_sq_size(per_group_segments[group].PerFrameFunctionalGroupsSequence)))
  ds = per_group_segments[group]
  ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRBigEndian
  ds.is_little_endian = False
  ds.is_implicit_VR = False
  # save the new dataset to a file
  ds.save_as(f"output_group_{group}.dcm", )
import os
import fileinput
import re

# Ask the user for input
commit_type = input("Are you preparing for a main or tag commit? (Enter 'main' or 'tag'): ")
tag = ""

# If the commit type is 'tag', ask for the tag name
if commit_type == 'tag':
    tag = input("Please enter the tag: ")

# Ask the user for the root directory
root_dir = input("Please enter the root directory: ")

# Traverse the directory structure
for foldername, subfolders, filenames in os.walk(root_dir):
    for filename in filenames:
        # Check if the file has one of the desired extensions
        if filename.endswith(('.ipynb', '.wdl', '.cwl')):
            filepath = os.path.join(foldername, filename)
            print(filepath)

            # Open the file and replace the text
            with fileinput.FileInput(filepath, inplace=True) as file:
                for line in file:
                    if commit_type == 'main':
                        # Replace the folder path for 'main' commit
                        line = re.sub(r"(ImagingDataCommons/CloudSegmentator/blob/).*?/(workflows/TotalSegmentator)", r"\1main/\2", line)
                        line = re.sub(r"(ImagingDataCommons/CloudSegmentator/)(?!blob/).*?/(workflows/TotalSegmentator)", r"\1main/\2", line)
                        # Replace the Docker image tag for 'main' commit
                        line = re.sub(r"\"?(imagingdatacommons/.*:).*\"?", r'"\1main"', line)
                    elif commit_type == 'tag':
                        # Replace the folder path for 'tag' commit with the provided tag
                        line = re.sub(r"(ImagingDataCommons/CloudSegmentator/blob/).*?/(workflows/TotalSegmentator)", fr"\1{tag}/\2", line)
                        line = re.sub(r"(ImagingDataCommons/CloudSegmentator/)(?!blob/).*?/(workflows/TotalSegmentator)", fr"\1{tag}/\2", line)
                        # Replace the Docker image tag for 'tag' commit with the provided tag
                        line = re.sub(r"\"?(imagingdatacommons/.*:).*\"?", fr'"\1{tag}"', line)
                    print(line, end='')

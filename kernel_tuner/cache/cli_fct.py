"""
This file cli_fct.py contains the helper functions used in cli.py.
This way, we can split the files correctly and not obtain messy code.
Merging now works, inspecting and conversion still needs to be completed.
"""

from .cache import Cache
from .file import read_cache, write_cache 
from .convert import convert_cache_file, convert_cache_to_t4

from pathlib import Path
from os import PathLike
from typing import List

from shutil import copyfile

import argparse
import json
import jsonschema


def fileExists(fileName: PathLike) -> bool:
    """Validates if the file specified by fileName even exists."""
    return Path(fileName).is_file()

def checkEquivalence(listOfFiles: List[PathLike]):
    """Checks equivalence of set parameters for files in `listOfFiles`.
    Assumes that all files have been validated.
    We use the first file (listOfFiles[0]) as our base file, and compare everything with that."""
    base_file = Cache.read(listOfFiles[0])

    for i in range(1, len(listOfFiles)):
        temp_file = Cache.read(listOfFiles[i])

        # Now the equivalence logic

        # Merging is yet to be updated to work with different schema versions.
        
        if (base_file.version != temp_file.version):
            raise ValueError(f"Error in merging; files '{listOfFiles[0]}' and '{listOfFiles[i]}' are not of the same schema version.")

        if (base_file.device_name != temp_file.device_name):
            raise ValueError(f"Error in merging; key 'device_name' is not equivalent for files '{listOfFiles[0]}' and '{listOfFiles[i]}'.")

        if (base_file.kernel_name != temp_file.kernel_name):
            raise ValueError(f"Error in merging; key 'kernel_name' is not equivalent for files '{listOfFiles[0]}' and '{listOfFiles[i]}'.")

        if (base_file.problem_size != temp_file.problem_size):
            raise ValueError(f"Error in merging; key 'problem_size' is not equivalent for files '{listOfFiles[0]}' and '{listOfFiles[i]}'.")

        if (base_file.objective != temp_file.objective):
            raise ValueError(f"Error in merging; key 'objective' is not equivalent for files '{listOfFiles[0]}' and '{listOfFiles[i]}'.")

        if (base_file.tune_params_keys != temp_file.tune_params_keys):
            raise ValueError(f"Error in merging; key 'tune_params_keys' is not equivalent for files '{listOfFiles[0]}' and '{listOfFiles[i]}'.")


def mergeFiles(listOfFiles: List[PathLike], ofile: PathLike):
    """Merges the actual files and writes to the file `ofile`."""
    """Assumes that all files have been validated."""
    # FIXME: Cannot be guaranteed that the order of the cachelines in the files is also kept when merging
    # From cache.py (json.load).

    resulting_output = Cache.read(listOfFiles[0])
    resulting_output.create(ofile, \
        device_name=resulting_output.device_name, \
        kernel_name=resulting_output.kernel_name, \
        problem_size=resulting_output.problem_size, \
        tune_params_keys=resulting_output.tune_params_keys, \
        tune_params=resulting_output.tune_params, \
        objective=resulting_output.objective)

    # We read so the ._filename changes for append
    resulting_output = Cache.read(ofile)

    # Now for each file add the cache content.
    # Does not check for duplicates
    for i in range(0, len(listOfFiles)):

        temp_file = Cache.read(listOfFiles[i])

        for line in temp_file.lines:
            if resulting_output.lines.get(line) != None:
                temp_line = temp_file.lines[line]
                tune_params = {key: temp_line[key] for key in temp_file.tune_params_keys}
                resulting_output.lines.append(time=temp_line["time"],
                             compile_time=temp_line["compile_time"],
                             verification_time=temp_line["verification_time"],
                             benchmark_time=temp_line["benchmark_time"],
                             strategy_time=temp_line["strategy_time"],
                             framework_time=temp_line["framework_time"],
                             timestamp=temp_file.lines.get(line).timestamp,
                             times=temp_line["times"],
                             GFLOP_per_s=temp_line["GFLOP/s"],
                             **tune_params)

            else:
                raise ValueError(f"Multiple entries in files for cacheline with key '{line}'.")



def cli_get(apRes: argparse.Namespace):
    """Checks if entry (string) `checkEntry` is inside file `in_file`, by using
    the `cache.py` library.
    Does not perform syntax checking on `checkEntry`."""

    in_file = Cache.read(apRes.infile[0])

    cache_line = in_file.lines.get(apRes.key)

    if cache_line == None:
        raise ValueError(f"Cacheline entry '{apRes.key}' is not contained in cachefile '{apRes.infile[0]}'.")

    else:
        print("[*] Cacheline entry '{}' content [*]\n\n************************".format(str(apRes.key)))
        print(dict(cache_line.items()))
        print("************************")



def cli_delete(apRes: argparse.Namespace):
    """
    Tries to remove entry `key` from file `in_file`, by using the
    `file.py` functions read_cache, write_cache. 
    We delete the json entry ["cache"][`removeEntry`] from the returned JSON object
    from read_cache, then use write_cache() to write the result to the desired output file
    `out_file`.
    First we check if the entry actually exists in the cachefile using the library. If not, there
    is nothing to do.
    """

    in_file = out_file = apRes.infile[0] 

    if (apRes.output != None):
        out_file = apRes.output 

    cache_file = Cache.read(in_file)

    
    if (cache_file.lines.get(apRes.key) == None):
        raise ValueError(f"Entry '{apRes.key}' is not contained in cachefile '{in_file}'.")


    # FIXME: want to use the "safe" library version instead of these functions.
    # library still needs to be updated.
    json_data = read_cache(in_file)

    del json_data["cache"][apRes.key]


    write_cache(json_data, out_file)

    print("\n[*] Writing to output file '{}' after removing entry '{}' completed.".format(str(out_file), str(apRes.key)))



def cli_convert(apRes: argparse.Namespace):
    """The main function for handling the version conversion of a cachefile."""
    read_file  = apRes.infile
    write_file = apRes.output

    if not fileExists(read_file):
        raise ValueError(f"Can not find file \"{read_file}\"")
    
    if write_file is not None and write_file[-5:] != ".json":
        raise ValueError(f"Please specify a .json file for the output file")
    
    # If no output file is specified, let the conversion overwrite the input file
    if write_file is None:
        write_file = read_file
    else:
        copyfile(read_file, write_file)
    
    convert_cache_file(filestr=write_file,
                       target_version=apRes.target)



def cli_t4(apRes: argparse.Namespace):
    """The main function for handling the T4 conversion of a cachefile. """
    read_file  = apRes.infile
    write_file = apRes.output

    if not fileExists(read_file):
        raise ValueError(f"Can not find file \"{read_file}\"")
    
    if write_file is not None and write_file[-5:] != ".json":
        raise ValueError(f"Please specify a .json file for the output file")
    
    cache = read_cache(read_file)

    t4_cache = convert_cache_to_t4(cache)

    write_cache(t4_cache, write_file)



def cli_merge(apRes: argparse.Namespace):
    """The main function for handling the merging of two or more cachefiles.
    First, we must validate the existence and validity of cachefiles, then we merge."""
    file_list = apRes.files

    if (len(file_list) < 2):
        raise ValueError(f"Not enough (< 2) files provided to merge.")
    # Perform validation, equivalence and after merge.

    for i in file_list:
        Cache.read(i)

    # Tobias: You would need to add convert to equivalent schema version function call here
    checkEquivalence(file_list)

    mergeFiles(file_list, apRes.output)

    print("[*] Merging finished. Output file: '{}'.".format(str(apRes.output)))


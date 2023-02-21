#!/usr/bin/env python
"""This is the minimal example from the README"""

import numpy
from collections import OrderedDict

import kernel_tuner
from kernel_tuner import tune_kernel, run_kernel
from kernel_tuner.file_utils import store_output_file, store_metadata_file
from kernel_tuner.core import KernelSource, DeviceInterface
from kernel_tuner.interface import (_kernel_options, _device_options,
                                    _check_user_input, Options)


def verify_kernel_string(kernel_name,
                         kernel_source,
                         problem_size,
                         arguments,
                         params,
                         device=0,
                         platform=0,
                         quiet=False,
                         compiler=None,
                         compiler_options=None,
                         block_size_names=None,
                         lang=None,
                         defines=None):
    grid_div_x=None
    grid_div_y=None
    grid_div_z=None
    smem_args=None
    cmem_args=None
    texmem_args=None

    # DeviceInterface has a compile_and_benchmark function
    kernelsource = KernelSource(kernel_name, kernel_source, lang, defines)

    _check_user_input(kernel_name, kernelsource, arguments, block_size_names)

    #sort options into separate dicts
    opts = locals()
    kernel_options = Options([(k, opts[k]) for k in _kernel_options.keys()])
    device_options = Options([(k, opts[k]) for k in _device_options.keys()])

    #detect language and create the right device function interface
    dev = DeviceInterface(kernelsource, iterations=1, **device_options)

    #TODO: MAKE PROPER TRY EXCEPT ETC>
    instance = None
    instance = dev.create_kernel_instance(kernelsource,
                                          kernel_options,
                                          params,
                                          True)
    if instance is None:
        raise RuntimeError("cannot create kernel instance,"+
                           " too many threads per block")
    # see if the kernel arguments have correct type
    kernel_tuner.util.check_argument_list(instance.name,
                                          instance.kernel_string,
                                          arguments)

    #compile the kernel
    func = dev.compile_kernel(instance, True)
    if func is None:
        raise RuntimeError("cannot compile kernel"+
                           " too much shared memory used")
    return kernel_options, device_options

CUDA_type_converter = {
    'int': int,
    'float': float,
    'bool': bool,
    'int*': 'numpy.int',
    'float*': numpy.float32,
    'bool*': 'numpy.bool',
}


def parse_function_sign(kernel_string, size=128):
    ###  Parse kernel name
    kernel_name = kernel_string.split("(")[0].split(" ")[-1]

    ###  Parse arguments to function, and create default python args
    args_str = kernel_string.split("(")[1].split(")")[0]
    args_str = args_str.replace(',', '').split(" ")
    args = dict()
    for k in range(0, len(args_str), 2):# Steps of 2
        CUDA_type_str = args_str[k]
        var_name = args_str[k+1]
        # Sometimes chatGPT/people put the * before the variable name
        if var_name[0] == '*':
            var_name = var_name[1:]
            CUDA_type_str += "*"

        python_type = CUDA_type_converter[CUDA_type_str]
        if 'numpy' in str(python_type):
            if str(python_type) == 'numpy.int':
                args[var_name] = numpy.random.randn(size).astype(int)
            elif str(python_type) == 'numpy.bool':
                args[var_name] = numpy.random.randn(size).astype(bool)
            else:
                args[var_name] = numpy.random.randn(size).astype(python_type)
        elif CUDA_type_str == 'int':
            # Guessing that we can assign 'size' to this int
            # This is because almost all kernels have some int param
            # that regulates the size of the for loop/array.
            value = numpy.int32(size)
            #value = python_type.__new__(python_type)
            #value = size
            args[var_name] = value
        else:
            value = python_type.__new__(python_type)
            args[var_name] = value

    ###  Parse tunable params
    #Select only those lines with dots in them
    tune_params_str = [x for x in kernel_string.split("\n") if '.' in x]

    # Clean it up
    tune_strs =  [x.replace("+", '') for x in tune_params_str]
    tune_strs =  [x.replace("-", '') for x in tune_strs]
    tune_strs =  [x.replace("=", '') for x in tune_strs]
    tune_strs =  [x.replace("*", '') for x in tune_strs]
    tune_strs =  [x.replace(";", '') for x in tune_strs]
    tune_strs =  [x.replace(",", '') for x in tune_strs]

    # Select potential candidates for tunable params
    # TODO: This will be hard to do accurately
    candidates = [y for x in tune_strs for y in x.split(" ")]
    #candidates = [x for x in candidates if '.' in x]
    candidates = [x for x in candidates if len(x) > 7]

    # Remove those with 'Idx' in the name because they are CUDA idx variables
    candidates = [x for x in candidates if 'Idx' not in x]

    # Dots in names are not "valid identifiers", so we replace them
    valid_cands = [x.replace(".", "") for x in candidates]
    for i in range(len(candidates)):
        kernel_string = kernel_string.replace(candidates[i], valid_cands[i])

    tune_params = dict()
    for cand in valid_cands:
        tune_params[cand] = 1
    return kernel_string, kernel_name, list(args.values()), tune_params


def setup_var_defs(kernel_options, tune_params):
    grid_div = (kernel_options.grid_div_x,
                kernel_options.grid_div_y,
                kernel_options.grid_div_z)

    threads, grid = kernel_tuner.util.setup_block_and_grid(
                        kernel_options.problem_size,
                        grid_div,
                        tune_params,
                        kernel_options.block_size_names)

    defines = OrderedDict()
    grid_dim_names = ["grid_size_x", "grid_size_y", "grid_size_z"]
    for i, g in enumerate(grid):
        defines[grid_dim_names[i]] = g
    for i, g in enumerate(threads):
        defines[kernel_options.block_size_names[i]] = g
    for k, v in tune_params.items():
        defines[k] = 256 # <--- again, how to set this in general?
    defines["kernel_tuner"] = 1
    return defines


def validate_kernel(kernel_string, size, compiler_options=None):
    # Parse as much as possible from the ChatGPT kernel string
    kernel_string, kernel_name, args, tune_params = parse_function_sign(
                                                         kernel_string,
                                                         size=size)

    # Verify if this kernel string compiles
    kernel_options, device_options = verify_kernel_string(kernel_name,
                         kernel_string,
                         size,
                         args,
                         tune_params,
                         compiler_options=compiler_options)
                         #compiler_options=['-Wno-deprecated-gpu-targets'])

    # Setup the variables for pre-definition
    defines = setup_var_defs(kernel_options, tune_params)

    # Run kernel
    run_kernel(kernel_name,
               kernel_string,
               size,
               args,
               tune_params,
               defines=defines,
               compiler_options=compiler_options)
    return kernel_name, kernel_string, size, args, tune_params, defines


if __name__ == "__main__":
    # Default array size for testing
    size = 100000


    """
    >> Query to ChatGPT:
        "Can you write a CUDA kernel for adding vectors"

    << Response:
        __global__ void add_vectors(float* a, float* b, float* c, int n) {
            int i = blockIdx.x * blockDim.x + threadIdx.x;
            if (i < n) {
                c[i] = a[i] + b[i];
            }
        }
    """

    kernel_string = """
    __global__ void add_vectors(float* a, float* b, float* c, int n) {
        int i = blockIdx.x * blockDim.x + threadIdx.x;
        if (i < n) {
            c[i] = a[i] + b[i];
        }
    }
    """

    kname, kstring, size, args, tune_params, defines = validate_kernel(
                    kernel_string,
                    size,
                    compiler_options=['-allow-unsupported-compiler'])

    """
    >> Query to ChatGPT:
        "Can you make it tunable?"

    << Response:
        __global__ void add_vectors(float* a, float* b, float* c, int n) {
            int tid = threadIdx.x + blockIdx.x * blockDim.x;
            int stride = blockDim.x * gridDim.x;

            for (int i = tid; i < n; i += stride) {
                c[i] = a[i] + b[i];
            }
        }
    """
    #NOTE: ChatGPT also told us that blockDim.x and gridDim.x are
    # tunable here
    kernel_string = """
    __global__ void add_vectors(float* a, float* b, float* c, int n) {
        int tid = threadIdx.x + blockIdx.x * blockDim.x;
        int stride = blockDim.x * gridDim.x;

        for (int i = tid; i < n; i += stride) {
            c[i] = a[i] + b[i];
        }
    }
    """

    kname, kstring, size, args, tune_params, defines = validate_kernel(
                    kernel_string,
                    size,
                    compiler_options=['-allow-unsupported-compiler'])


    # CHAT GPT TIMED OUT, another try:
    kernel_string = """
    __global__ void vectorAdd(float *a, float *b, float *c, int n)
    {
        int idx = blockIdx.x * blockDim.x + threadIdx.x;

        if (idx < n) {
            c[idx] = a[idx] + b[idx];
        }
    }
    """

    kname, kstring, size, args, tune_params, defines = validate_kernel(
                    kernel_string,
                    size,
                    compiler_options=['-allow-unsupported-compiler'])


    #Make it tunable: this returned the same thing
    kernel_string = """
    __global__ void vectorAdd(float *a, float *b, float *c, int n)
    {
        int idx = blockIdx.x * blockDim.x + threadIdx.x;

        if (idx < n) {
            c[idx] = a[idx] + b[idx];
        }
    }
    """

    kname, kstring, size, args, tune_params, defines = validate_kernel(
                    kernel_string,
                    size,
                    compiler_options=['-allow-unsupported-compiler'])

    # Ask chatGPT for good tuning range:
    # What would be a good range for blockDim.x tuning?
    # << It gave a long story about how to choose it

    # Ask chatGPT for a list of numbers: got this:
    tune_values = [32, 64, 96, 128, 192, 256, 384, 512, 768, 1024]
    for k,v in tune_params.items():
        tune_params[k] = tune_values
    print(tune_params)

    # Run tuning with these parsed values:
    results, env = tune_kernel(kname,
                               kstring,
                               size,
                               args,
                               tune_params,
                               defines=defines,
                               compiler_options=['-allow-unsupported-compiler'])

    # Store the tuning results in an output file
    store_output_file("ChatGPT_vector_add.json", results, tune_params)

    # Store the metadata of this run
    store_metadata_file("ChatGPT_vector_add-metadata.json")

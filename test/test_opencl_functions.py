import numpy
from nose.tools import nottest
from .context import opencl, skip_if_no_opencl

try:
    import pyopencl
except Exception:
    pass


def test_create_gpu_args():

    skip_if_no_opencl()

    size = 1000
    a = numpy.int32(75)
    b = numpy.random.randn(size).astype(numpy.float32)
    c = numpy.zeros_like(b)

    arguments = [c, a, b]

    dev = opencl.OpenCLFunctions(0)
    gpu_args = dev.create_gpu_args(arguments)

    assert isinstance(gpu_args[0], pyopencl.Buffer)
    assert isinstance(gpu_args[1], numpy.int32)
    assert isinstance(gpu_args[2], pyopencl.Buffer)

    gpu_args[0].release()
    gpu_args[2].release()

def test_compile():

    skip_if_no_opencl()

    original_kernel = """
    __kernel void sum(__global const float *a_g, __global const float *b_g, __global float *res_g) {
        int gid = get_global_id(0);
        __local float test[shared_size];
        test[0] = a_g[gid];
        res_g[gid] = test[0] + b_g[gid];
    }
    """

    kernel_string = original_kernel.replace("shared_size", str(100*1024*1024))

    dev = opencl.OpenCLFunctions(0)
    func = dev.compile("sum", kernel_string)

    assert isinstance(func, pyopencl.Kernel)


@nottest
def test_func(queue, a, b, block=0, grid=0):
    profile = type('profile', (object,), {'end': 0.1, 'start': 0})
    return type('Event', (object,), {'wait': lambda self: 0, 'profile': profile()})()

def test_benchmark():
    skip_if_no_opencl()
    dev = opencl.OpenCLFunctions(0)
    args = [1, 2]
    time = dev.benchmark(test_func, args, (1,2,3), (1,2))
    assert time > 0



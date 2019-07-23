from setuptools import setup
from setuptools.extension import Extension
from distutils.command.build import build
from distutils.command.build_ext import build_ext
from distutils.util import get_platform
import os


BUILD_CUDA = ('FAISS_BUILD_CUDA' in os.environ)
PACKAGE_NAME = 'faiss-cu%s' % os.getenv('CUDA_VERSION', '7.5').replace(
    '.', ''
) if BUILD_CUDA else 'faiss-cpu'
LONG_DESCRIPTION = """
Faiss is a library for efficient similarity search and clustering of dense
vectors. It contains algorithms that search in sets of vectors of any size, up
to ones that possibly do not fit in RAM. It also contains supporting code for
evaluation and parameter tuning. Faiss is written in C++ with complete wrappers
for Python/numpy. It is developed by Facebook AI Research.
"""


class CustomBuild(build):
    """Build ext first so that swig-generated file is packaged.
    """
    sub_commands = [
        ('build_ext', build.has_ext_modules),
        ('build_py', build.has_pure_modules),
        ('build_clib', build.has_c_libraries),
        ('build_scripts', build.has_scripts),
    ]


class CustomBuildExt(build_ext):
    """Customize extension build.
    """

    def run(self):
        # Import NumPy only at runtime.
        import numpy
        self.include_dirs.append(numpy.get_include())
        link_flags = os.getenv('FAISS_LDFLAGS')
        if link_flags:
            if self.link_objects is None:
                self.link_objects = []
            for flag in link_flags.split():
                self.link_objects.append(flag.strip())
        else:
            self.libraries.append('faiss')
            if BUILD_CUDA:
                self.libraries.extend([
                    'cudart_static', 'cublas_static', 'culibos'
                ])
        build_ext.run(self)

    def build_extensions(self):
        # Suppress -Wstrict-prototypes bug in python.
        # https://stackoverflow.com/questions/8106258/
        self._remove_flag('-Wstrict-prototypes')
        # Remove clang-specific flag.
        compiler_name = self.compiler.compiler[0]
        if 'gcc' in compiler_name or 'g++' in compiler_name:
            self._remove_flag('-Wshorten-64-to-32')
        build_ext.build_extensions(self)

    def _remove_flag(self, flag):
        compiler = self.compiler.compiler
        compiler_cxx = self.compiler.compiler_cxx
        compiler_so = self.compiler.compiler_so
        for args in (compiler, compiler_cxx, compiler_so):
            while flag in args:
                args.remove(flag)


_swigfaiss = Extension(
    'faiss._swigfaiss',
    sources=['python/swigfaiss.i'],
    define_macros=[('FINTEGER', 'int')],
    language='c++',
    library_dirs=[
        os.getenv('CUDA_HOME', '/usr/local/cuda') + '/lib64',
    ],
    include_dirs=[
        os.getenv('FAISS_INCLUDE', '/usr/local/include/faiss'),
        os.getenv('CUDA_HOME', '/usr/local/cuda') + '/include',
    ],
    extra_compile_args=[
        '-std=c++11', '-mavx2', '-mf16c', '-msse4', '-mpopcnt', '-m64',
        '-Wno-sign-compare', '-fopenmp'
    ],
    extra_link_args=['-fopenmp'],
    swig_opts=[
        '-c++', '-Doverride=',
        '-I' + os.getenv('FAISS_INCLUDE', '/usr/local/include/faiss'),
        '-I' + os.getenv('CUDA_HOME', '/usr/local/cuda') + '/include'
    ] + ([] if 'macos' in get_platform() else ['-DSWIGWORDSIZE64']) +
    (['-DGPU_WRAPPER'] if BUILD_CUDA else []),
)

setup(
    name=PACKAGE_NAME,
    version='1.5.2',
    description=(
        'A library for efficient similarity search and clustering of dense '
        'vectors.'
    ),
    long_description=LONG_DESCRIPTION,
    url='https://github.com/kyamagu/faiss-wheels',
    author='Kota Yamaguchi',
    author_email='KotaYamaguchi1984@gmail.com',
    license='MIT',
    keywords='search nearest neighbors',
    cmdclass={
        'build': CustomBuild,
        'build_ext': CustomBuildExt,
    },
    install_requires=['numpy'],
    package_dir={'faiss': 'python'},
    packages=['faiss'],
    ext_modules=[_swigfaiss]
)

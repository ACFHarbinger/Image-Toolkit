cmake -B desktop/build
cmake --build desktop/build
cd desktop/build
ctest
rm -rf _deps
rm -rf bin
rm -rf CMakeFiles
rm -rf lib
rm -rf Testing
rm -rf cmake_install.cmake
rm -rf CMakeCache.txt
rm -rf CTestTestfile.cmake
rm -rf FileSystemTests
rm -rf ImageConverterTests
rm -rf ImageMergerTests
rm -rf libImageToolkitCore.a
rm -rf Makefile
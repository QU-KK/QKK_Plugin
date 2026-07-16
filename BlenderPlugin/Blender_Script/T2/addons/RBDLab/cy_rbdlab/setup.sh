#!/bin/bash

#-----------------------------------------------------------------
# Instalar python 3.11.7 con pyenv:
#-----------------------------------------------------------------
#
# [En linux]:
#     Arch:
#         sudo pacman -S pyenv 
#
#     Debian testing:
#         sudo apt install make/testing build-essential/testing libssl-dev/testing zlib1g-dev/testing libbz2-dev/testing libreadline-dev/testing libsqlite3-dev/testing wget/testing curl/testing llvm/testing libncurses5-dev/testing libncursesw5-dev/testing xz-utils/testing tk-dev/testing libffi-dev/testing liblzma-dev/testing python3-openssl/testing git/testing zlib1g-dev/testing libgdbm-dev/testing libdb5.3-dev/testing libexpat1-dev/testing
#         git clone https://github.com/pyenv/pyenv.git ~/.pyenv
#         echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
#         echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
#         echo 'eval "$(pyenv init --path)"' >> ~/.bashrc
#                  
# [En Mac]:
#     instalamos brew: 
#        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
#     brew install pyenv

#-----------------------------------------------------------------
# Common Linux/Mac
#-----------------------------------------------------------------
# cd cy_rbdlab
# pyenv install 3.11.7  # <- with this command install python 3.11.7
# ~/.pyenv/versions/3.11.7/bin/pip install --upgrade pip
# ~/.pyenv/versions/3.11.7/bin/pip install -r requirments.txt

#-----------------------------------------------------------------
# To compile:
#-----------------------------------------------------------------
# cd cy_rbdlab
# ./setup.sh

PYTHON_VER="3.11.7"
PYTHON_SHORT_VER="311"

# Para detectar si es Mac o Linux:
unameOut="$(uname -s)"
case "${unameOut}" in
    Linux*)     machine=Linux;;
    Darwin*)    machine=Mac;;
    CYGWIN*)    machine=Cygwin;;
    MINGW*)     machine=MinGw;;
    MSYS_NT*)   machine=Git;;
    *)          machine="UNKNOWN:${unameOut}"
esac

machine=${machine}

if [ "$machine" = "Linux" ] ; then 
  FILE_OUTPUT_NAME="distances_lnx.cpython-$PYTHON_SHORT_VER-x86_64-linux-gnu.so";
  FILE_RESULT_FOR_IMPORT="distances_lnx.so";

elif [ "$machine" = "Mac" ] ; then 

  arch_name="$(uname -m)"
 
  if [ "${arch_name}" = "x86_64" ]; then
    echo "Running on Mac Intel"
    FILE_OUTPUT_NAME="distances_mac_intel.cpython-$PYTHON_SHORT_VER-darwin.so";
    FILE_RESULT_FOR_IMPORT="distances_mac_intel.so";
    
  elif [ "${arch_name}" = "arm64" ]; then
    echo "Running on Mac ARM"
    FILE_OUTPUT_NAME="distances_mac_arm.cpython-$PYTHON_SHORT_VER-darwin.so";
    FILE_RESULT_FOR_IMPORT="distances_mac_arm.so";

  fi


fi

HTML_DIST_FILE="distances.html"
C_DIST_FILE="distances.c"
CPP_FILE="distances.cpp"
BUILD_DIR="build"

remove_file() {
  if [ -f $1 ]; then
    rm $1
    echo "$1 is removed"
  fi
}

remove_directory() {
  if [ -d $1 ]; then
    rm -fR $1
    echo "Directory $1 removed."
  fi
}

remove_file $HTML_DIST_FILE
remove_file $C_DIST_FILE
remove_file $CPP_FILE
remove_directory $BUILD_DIR
remove_file $FILE_RESULT_FOR_IMPORT

~/.pyenv/versions/$PYTHON_VER/bin/python setup.py build_ext --inplace

remove_file $C_DIST_FILE
remove_directory $BUILD_DIR
remove_file $CPP_FILE

if [ -f $FILE_OUTPUT_NAME ]; then
    mv $FILE_OUTPUT_NAME $FILE_RESULT_FOR_IMPORT
    echo "File $FILE_OUTPUT_NAME renamed to $FILE_RESULT_FOR_IMPORT"
fi

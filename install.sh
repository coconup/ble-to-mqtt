#!/bin/bash

# Check if Git is installed
if ! command -v git &> /dev/null; then
    echo "Git is not installed. Please install Git before running this script."
    exit 1
fi

# Define the installation directory
install_dir="./lib"

# Clone the repositories
git clone "https://github.com/coconup/renogy-bt.git" "$install_dir/renogy-bt"
git clone "https://github.com/coconup/batmon-ha.git" "$install_dir/batmon-ha"

# Check if the clone was successful
if [ $? -eq 0 ]; then
    echo "Repositories successfully cloned to $install_dir"
else
    echo "Failed to clone the repository. Check the URL and try again."
    exit 1
fi

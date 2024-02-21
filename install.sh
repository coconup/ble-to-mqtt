#!/bin/bash

# Define the repository URL
repo_url="https://github.com/coconup/renogy-bt.git"

# Define the installation directory
install_dir="/lib/renogy-bt"

# Check if Git is installed
if ! command -v git &> /dev/null; then
    echo "Git is not installed. Please install Git before running this script."
    exit 1
fi

# Clone the repository
git clone "$repo_url" "$install_dir"

# Check if the clone was successful
if [ $? -eq 0 ]; then
    echo "Repository successfully cloned to $install_dir"
else
    echo "Failed to clone the repository. Check the URL and try again."
    exit 1
fi

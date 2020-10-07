#!/bin/bash
changed_dirs=$(git diff --name-only HEAD HEAD~30 | xargs dirname | cut -d "/" -f1 | uniq)
echo "$changed_dirs" | while read dir; do
    echo $dir
    docker ps -qf "name=$dir"
    echo ""
done

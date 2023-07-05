#!/bin/sh

# Set to 1 (or any non 0) value to see debug path data
debug=0

currentpath=$1

if [ $debug -ne 0 ]; then echo Testing path - $currentpath; fi

# Initialize and attempt to create the path as is
nonwslpath=''
output=$( (wslpath -w $currentpath) 2>&1 )
retval=$?

while [ $retval -ne 0 ]; do
    if [ $debug -ne 0 ]; then printf 'wp: %s - %s\n' "$output" "$nonwslpath"; fi

    # Strip off the tip of the path and store as part of oue unconvertible bit
    #   That bit will be appended to the path that can be converted (if any)
    #   NOTE: The nonwslpath is reversed! It will be fixed at the end
    if [ "$nonwslpath" != "" ]; then
        nonwslpath=$nonwslpath\\$(echo $currentpath | rev | cut -d '/' -f1)
    else
        nonwslpath=$(echo $currentpath | rev | cut -d '/' -f1)
    fi
    if [ $debug -ne 0 ]; then printf 'np: %s\n' "$nonwslpath"; fi

    # The current path for converting will has the last bit removed
    currentpath=$(echo $currentpath | rev | cut -s -d '/' -f2- | rev)
    if [ $debug -ne 0 ]; then printf 'cp: %s\n' "$currentpath"; fi

    # If there's nothing left use the current directory as the root, or try to convert
    # what's left after removing the tip
    if [ "$currentpath" != "" ]; then
        output=$( (wslpath -w $currentpath) 2>&1 )
    else
        output=$( (wslpath -w ./) 2>&1 )
    fi
    retval=$?

    if [ $debug -ne 0 ]; then printf 'wp2: %s - %s\n' "$output" "$nonwslpath"; fi
done

# If there's any nonconverted wsl path, add it to the converted version of the wslpath
# This path is reversed and needs to reversed to be right way round
if [ "$nonwslpath" != "" ]; then
    nonwslpath=$(printf "%s" "$nonwslpath" | rev)
    printf '%s\\%s\n' "$output" "$nonwslpath"
else
    printf '%s\n' "$output"
fi

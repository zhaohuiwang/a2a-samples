#!/bin/bash

# A script to find and replace camelCase fields with their snake_case equivalents
# For updating to A2A SDK v0.2.16 and later.

# --- Configuration ---
# List of all camelCase fields to be replaced.
CAMEL_CASE_FIELDS=(
    'securitySchemes'
    'messageId'
    'taskId'
    'contextId'
    'referenceTaskIds'
    'supportsAuthenticatedExtendedCard'
    'inputModes'
    'outputModes'
    'authorizationUrl'
    'refreshUrl'
    'tokenUrl'
    'bearerFormat'
    'openIdConnectUrl'
    'historyLength'
    'pushNotifications'
    'stateTransitionHistory'
    'acceptedOutputModes'
    'pushNotificationConfig'
    'authorizationCode'
    'clientCredentials'
    'artifactId'
    'lastChunk'
    'additionalInterfaces'
    'defaultInputModes'
    'defaultOutputModes'
    'documentationUrl'
    'iconUrl'
    'preferredTransport'
    'protocolVersion'
    'pushNotificationConfigId'
    'mimeType'
)

# --- Functions ---

# Function to display usage information.
usage() {
    echo "Usage: $0 [options] <directory>"
    echo
    echo "Finds and replaces camelCase fields with snake_case fields in a codebase."
    echo
    echo "Options:"
    echo "  --dry-run   Show which files would be changed without modifying them."
    echo "  -h, --help  Display this help message."
    echo
    echo "Example:"
    echo "  $0 --dry-run ./src"
    echo "  $0 ./src"
    exit 1
}

# Function to convert a camelCase string to snake_case.
# Uses sed for the conversion.
camel_to_snake() {
    echo "$1" | sed -E 's/([a-z0-9])([A-Z])/\1_\2/g' | tr '[:upper:]' '[:lower:]'
}

# --- Main Script Logic ---

# Initialize variables
DRY_RUN=0
DIRECTORY=""

# Parse command-line arguments
while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        -h|--help)
            usage
            ;;
        -*)
            echo "Unknown option: $1"
            usage
            ;;
        *)
            if [[ -z "$DIRECTORY" ]]; then
                DIRECTORY="$1"
            else
                echo "Error: Multiple directories specified."
                usage
            fi
            shift
            ;;
    esac
done

# Check if directory is provided
if [[ -z "$DIRECTORY" ]]; then
    echo "Error: No directory specified."
    usage
fi

# Check if directory exists
if [[ ! -d "$DIRECTORY" ]]; then
    echo "Error: Directory '$DIRECTORY' not found."
    exit 1
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "--- Starting DRY RUN. No files will be modified. ---"
else
    echo "--- Starting refactoring. Files will be modified in-place. ---"
fi
echo "Targeting directory: $DIRECTORY"
echo "----------------------------------------------------"

# Loop through each field and perform the replacement
for camel_field in "${CAMEL_CASE_FIELDS[@]}"; do
    snake_field=$(camel_to_snake "$camel_field")

    # Skip if conversion results in the same name (shouldn't happen with this list)
    if [[ "$camel_field" == "$snake_field" ]]; then
        continue
    fi

    echo "Processing: $camel_field -> $snake_field"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        # In dry run mode, just find files that contain the term.
        # Use grep with word boundaries. The -l flag lists filenames only.
        files_found=$(find "$DIRECTORY" -type f -name "*.py" -print0 | xargs -0 grep -l "\b$camel_field\b" 2>/dev/null)
        if [[ -n "$files_found" ]]; then
            echo "  [WOULD CHANGE] in files:"
            # Indent the list of files for readability
            echo "$files_found" | sed 's/^/    /'
        else
            echo "  [NO CHANGE] No occurrences found."
        fi
    else
        # In live mode, use perl to perform in-place replacement.
        # -print0 and xargs -0 handle filenames with spaces correctly.
        # The \b ensures we match whole words only.
        find "$DIRECTORY" -type f -name "*.py" -print0 | xargs -0 perl -pi -e "s/\b$camel_field\b/$snake_field/g" 2>/dev/null
    fi
    echo
done

echo "----------------------------------------------------"
echo "Script finished."
if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "To apply changes, run the script again without the --dry-run flag."
fi

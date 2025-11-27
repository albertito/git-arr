#!/bin/bash
#
# Set KEEP_TEMP=1 to preserve the temporary directory after the test.
# Set COVERAGE=1 to generate coverage reports with python3-coverage.
# Set PROFILE=1 to generate profiling data with cProfile.

set -e -u

KEEP_TEMP=${KEEP_TEMP:-0}
COVERAGE=${COVERAGE:-0}
PROFILE=${PROFILE:-0}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Run git-arr with debug logging, to get timing information.
export GIT_ARR_DEBUG=1

# Check for mutually exclusive options.
if [ "$PROFILE" = 1 ] && [ "$COVERAGE" = 1 ]; then
    echo "Error: PROFILE and COVERAGE cannot both be enabled" >&2
    exit 1
fi

# Set up profiling or coverage if requested.
if [ "$PROFILE" = 1 ]; then
    INITIAL_PROF="$SCRIPT_DIR/.logs/initial_generation.prof"
    INCREMENTAL_PROF="$SCRIPT_DIR/.logs/incremental_generation.prof"
    RUNNER_INITIAL="python3 -m cProfile -o $INITIAL_PROF"
    RUNNER_INCREMENTAL="python3 -m cProfile -o $INCREMENTAL_PROF"
elif [ "$COVERAGE" = 1 ]; then
    export COVERAGE_FILE="$SCRIPT_DIR/.logs/coverage"
    RUNNER_INITIAL="python3-coverage run -a --source=."
    RUNNER_INCREMENTAL="$RUNNER_INITIAL"
else
    RUNNER_INITIAL=""
    RUNNER_INCREMENTAL=""
fi

# Create temporary directory.
TEMP_DIR=$(mktemp -d -t git-arr-perf.XXXXXX)

echo "Temporary directory: $TEMP_DIR"

# Paths.
TMP_REPO="$TEMP_DIR/git-arr"
OUTPUT_DIR="$TEMP_DIR/output"
CONFIG_FILE="$TEMP_DIR/test.conf"
INITIAL_LOG="$SCRIPT_DIR/.logs/initial_generation.log"
INITIAL_DEBUG_LOG="$SCRIPT_DIR/.logs/initial_generation_debug.log"
INCREMENTAL_LOG="$SCRIPT_DIR/.logs/incremental_generation.log"
INCREMENTAL_DEBUG_LOG="$SCRIPT_DIR/.logs/incremental_generation_debug.log"

echo "Cloning git-arr repository..."
git clone -q "$REPO_ROOT" "$TMP_REPO"

# Generate config file.
sed "s|TEMPDIR_PLACEHOLDER|$TEMP_DIR|g" "$SCRIPT_DIR/perf_test.conf" > "$CONFIG_FILE"

# Create output directory, and logs directory.
mkdir -p "$OUTPUT_DIR" "$SCRIPT_DIR/.logs/"

cd "$REPO_ROOT"


# Run initial generation.
echo "Initial generation"
$RUNNER_INITIAL ./git-arr --config "$CONFIG_FILE" generate --output "$OUTPUT_DIR" \
	> "$INITIAL_LOG" \
	2> "$INITIAL_DEBUG_LOG" \
	|| cat "$INITIAL_LOG"

# Modify files in the cloned repo.
echo "# Performance test run: $(date)" >> "$TMP_REPO/README.md"
echo '# Modified for performance testing' >> "$TMP_REPO/git-arr"
echo '# Modified for performance testing' >> "$TMP_REPO/utils.py"

# Commit changes.
cd "$TMP_REPO"
git add README.md git-arr utils.py
git commit -q -m "Performance test: modified files"
echo "Test commit: $(git rev-parse --short HEAD)"
cd "$REPO_ROOT"

# Run incremental generation.
echo "Incremental generation"
$RUNNER_INCREMENTAL ./git-arr --config "$CONFIG_FILE" generate --output "$OUTPUT_DIR" \
	> "$INCREMENTAL_LOG" \
	2> "$INCREMENTAL_DEBUG_LOG" \
	|| cat "$INCREMENTAL_LOG"

echo "Logs saved to $SCRIPT_DIR/.logs/"

if [ "$COVERAGE" = 1 ]; then
    echo
    echo "Coverage report:"
    python3-coverage report
    python3-coverage html -q -d "$SCRIPT_DIR/.logs/htmlcov"
    echo
    echo "HTML coverage report: file://$SCRIPT_DIR/.logs/htmlcov/index.html"
fi


pyprof_summary() {
	python3 -c "import pstats; \
		p = pstats.Stats('$1'); \
		p.sort_stats('cumulative'); \
		p.print_stats(20)"
}

if [ "$PROFILE" = 1 ]; then
    echo
    echo "Profile report (initial generation):"
    pyprof_summary "$INITIAL_PROF"

    echo
    echo "Profile report (incremental generation):"
    pyprof_summary "$INCREMENTAL_PROF"

    echo
    echo "Profile data saved:"
    echo "  Initial:      $INITIAL_PROF"
    echo "  Incremental:  $INCREMENTAL_PROF"
fi

if [ "$KEEP_TEMP" = 0 ]; then
    echo "Cleaning up temporary directory"
    rm -rf "$TEMP_DIR"
fi

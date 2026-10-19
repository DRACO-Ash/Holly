#!/bin/sh
# check-lcov.sh :: the dashboard's coverage report must name exactly the files under frontend/src
# that are not tests (the dashboard's source and its two test helpers), each by its path from the
# repository's root, since the Code Quality gate scores a file the report leaves out, or names by
# a path it cannot find, at 0%. verify.sh runs it on the repository; simulate-pipeline.sh runs it
# on the node job's checkout. Usage: sh scripts/check-lcov.sh [<root>] (default: the current
# directory)
set -eu
cd "${1:-.}"
test -s coverage/lcov.info || {
  echo "FAIL: coverage/lcov.info is missing or empty; the Code Quality gate would score the dashboard at 0%"
  exit 1
}
listed="$(sed -n 's/^SF://p' coverage/lcov.info | LC_ALL=C sort)"
files="$(find frontend/src -type f \( -name '*.ts' -o -name '*.tsx' \) ! -name '*.d.ts' \
  ! -name '*.test.ts' ! -name '*.test.tsx' | LC_ALL=C sort)"
if [ "$listed" != "$files" ]; then
  echo "FAIL: coverage/lcov.info does not name exactly the files under frontend/src that are not tests:"
  printf '%s\n' "$files" | while IFS= read -r f; do
    printf '%s\n' "$listed" | grep -qxF -- "$f" || printf '  missing from the report: %s\n' "$f"
  done
  printf '%s\n' "$listed" | while IFS= read -r f; do
    printf '%s\n' "$files" | grep -qxF -- "$f" || printf '  named, but no such file: %s\n' "$f"
  done
  exit 1
fi
echo "coverage/lcov.info names all $(printf '%s\n' "$files" | wc -l | tr -d ' ') files under frontend/src that are not tests"

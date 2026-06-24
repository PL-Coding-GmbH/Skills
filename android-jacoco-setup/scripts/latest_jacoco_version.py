#!/usr/bin/env python3
"""Print the latest org.jacoco:org.jacoco.core version from Maven Central.

The Gradle `jacoco` plugin's report engine is pinned via `jacoco { toolVersion = ... }`,
and that version is the `org.jacoco.core` coordinate. We query Maven Central's search
API for it so the setup always uses the current release rather than a hardcoded one.
"""

import json
import sys
import urllib.request

SEARCH_URL = (
    "https://search.maven.org/solrsearch/select?"
    "q=g:%22org.jacoco%22+AND+a:%22org.jacoco.core%22&rows=1&wt=json"
)


def main():
    try:
        with urllib.request.urlopen(SEARCH_URL, timeout=15) as response:
            data = json.load(response)
    except Exception as error:  # network, JSON, HTTP — all surface the same way
        print(f"Failed to query Maven Central: {error}", file=sys.stderr)
        return 1

    docs = data.get("response", {}).get("docs", [])
    if not docs or "latestVersion" not in docs[0]:
        print("Could not determine the latest org.jacoco.core version.", file=sys.stderr)
        return 1

    print(docs[0]["latestVersion"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

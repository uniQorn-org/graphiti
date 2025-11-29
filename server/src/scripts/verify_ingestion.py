#!/usr/bin/env python3
"""Verification queries for checking ingestion quality.

This script runs a series of Cypher queries against Neo4j to verify:
1. Entity uniqueness (no duplicate users)
2. Timestamp format validity
3. Timeline consistency
4. Overall entity statistics
"""

import subprocess
import sys
from datetime import datetime


class Colors:
    """ANSI color codes for terminal output."""
    BLUE = '\033[0;34m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[0;33m'
    RED = '\033[0;31m'
    NC = '\033[0m'  # No Color


def run_query(query: str, description: str) -> str:
    """Run a Cypher query against Neo4j and return the output."""
    print(f"\n{Colors.BLUE}=== {description} ==={Colors.NC}")

    cmd = [
        "docker-compose", "exec", "-T", "neo4j",
        "cypher-shell", "-u", "neo4j", "-p", "password123",
        query
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"{Colors.RED}Error running query:{Colors.NC}")
        print(e.stderr)
        return ""


def check_duplicate_users():
    """Check for duplicate user entities."""
    query = """
    MATCH (e:Entity)
    WHERE e.name CONTAINS 'U0' OR e.name CONTAINS 'Unknown'
    WITH e.name as entity_name, count(*) as entity_count
    WHERE entity_count > 1
    RETURN entity_name, entity_count
    ORDER BY entity_count DESC
    """

    output = run_query(query, "Checking for Duplicate User Entities")
    print(output)

    lines = output.strip().split('\n')
    # Check if there are any data rows (beyond header)
    has_duplicates = len(lines) > 1 and any(line.strip() for line in lines[1:])

    if "Unknown" in output or has_duplicates:
        print(f"{Colors.YELLOW}⚠️  Warning: Duplicate entities found{Colors.NC}")
        return False
    else:
        print(f"{Colors.GREEN}✓ No duplicate entities found{Colors.NC}")
        return True


def check_timestamp_format():
    """Check for invalid timestamp formats in valid_at fields."""
    query = """
    MATCH ()-[r]->()
    WHERE exists(r.valid_at)
    WITH r.valid_at as timestamp
    WHERE timestamp =~ '.*\\?\\?.*' OR NOT timestamp =~ '\\d{4}-\\d{2}-\\d{2}.*'
    RETURN timestamp, count(*) as invalid_count
    """

    output = run_query(query, "Checking Timestamp Format Validity")
    print(output)

    # Check if any invalid timestamps were found
    lines = output.strip().split('\n')
    if len(lines) > 1 and lines[1].strip():  # Has data beyond header
        print(f"{Colors.RED}✗ Invalid timestamps found{Colors.NC}")
        return False
    else:
        print(f"{Colors.GREEN}✓ All timestamps are valid{Colors.NC}")
        return True


def check_timeline():
    """Check timeline of episodes."""
    query = """
    MATCH (e:Episodic)
    RETURN e.name as episode, e.created_at as timestamp
    ORDER BY e.created_at
    LIMIT 20
    """

    output = run_query(query, "Timeline of First 20 Episodes")
    print(output)

    # Verify timestamps are in chronological order
    lines = output.strip().split('\n')[1:]  # Skip header
    timestamps = []
    for line in lines:
        if line.strip():
            parts = line.split(',')
            if len(parts) >= 2:
                ts_str = parts[1].strip().strip('"')
                if ts_str and ts_str != 'null':
                    try:
                        timestamps.append(datetime.fromisoformat(ts_str.replace('Z', '+00:00')))
                    except ValueError:
                        pass

    if len(timestamps) > 1:
        is_sorted = all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1))
        if is_sorted:
            print(f"{Colors.GREEN}✓ Timeline is chronologically ordered{Colors.NC}")
            return True
        else:
            print(f"{Colors.YELLOW}⚠️  Warning: Timeline may not be chronologically ordered{Colors.NC}")
            return False

    return True


def check_entity_stats():
    """Get entity statistics."""
    query = """
    MATCH (n)
    RETURN labels(n)[0] as type, count(n) as count
    ORDER BY count DESC
    """

    output = run_query(query, "Entity Statistics")
    print(output)

    # Parse output to check for "Unknown" entities
    if "Unknown" in output:
        print(f"{Colors.YELLOW}⚠️  Warning: 'Unknown' entities present in graph{Colors.NC}")
        return False
    else:
        print(f"{Colors.GREEN}✓ Entity distribution looks good{Colors.NC}")
        return True


def check_user_entities():
    """Check all user entities by name pattern."""
    query = """
    MATCH (e:Entity)
    WHERE e.name =~ 'U[0-9A-Z]+.*'
    RETURN e.name as user_entity, count(*) as occurrence_count
    ORDER BY occurrence_count DESC
    """

    output = run_query(query, "User Entities (Slack User IDs)")
    print(output)

    # Count total user entities
    lines = output.strip().split('\n')[1:]  # Skip header
    user_count = len([l for l in lines if l.strip()])

    print(f"\n{Colors.BLUE}Total unique user entities: {user_count}{Colors.NC}")
    return True


def check_timestamp_distribution():
    """Check the distribution of timestamps across episodes."""
    query = """
    MATCH (e:Episodic)
    WHERE e.created_at IS NOT NULL
    WITH e.created_at as ts
    ORDER BY ts
    WITH collect(ts) as timestamps
    RETURN
        timestamps[0] as earliest,
        timestamps[-1] as latest,
        size(timestamps) as total_episodes
    """

    output = run_query(query, "Timestamp Distribution")
    print(output)

    # Parse to check if timestamps span actual Slack message times
    lines = output.strip().split('\n')
    if len(lines) > 1:
        data = lines[1].split(',')
        if len(data) >= 3:
            earliest = data[0].strip().strip('"')
            latest = data[1].strip().strip('"')
            total = data[2].strip()

            print(f"\n{Colors.BLUE}Earliest episode: {earliest}{Colors.NC}")
            print(f"{Colors.BLUE}Latest episode: {latest}{Colors.NC}")
            print(f"{Colors.BLUE}Total episodes: {total}{Colors.NC}")

            # Check if timestamps are from the past (not current time)
            try:
                latest_dt = datetime.fromisoformat(latest.replace('Z', '+00:00'))
                now = datetime.now(latest_dt.tzinfo)

                # If latest timestamp is more than 1 hour old, it's likely using actual message times
                time_diff = (now - latest_dt).total_seconds() / 3600
                if time_diff > 1:
                    print(f"{Colors.GREEN}✓ Timestamps appear to use actual message times (not current time){Colors.NC}")
                    return True
                else:
                    print(f"{Colors.YELLOW}⚠️  Warning: Timestamps may be using current time instead of message times{Colors.NC}")
                    return False
            except ValueError:
                pass

    return True


def main():
    """Run all verification checks."""
    print(f"{Colors.BLUE}")
    print("=" * 70)
    print("   Graphiti Ingestion Verification")
    print("=" * 70)
    print(f"{Colors.NC}")

    results = []

    # Run all checks
    results.append(("Duplicate Users", check_duplicate_users()))
    results.append(("Timestamp Format", check_timestamp_format()))
    results.append(("Timeline Order", check_timeline()))
    results.append(("Entity Stats", check_entity_stats()))
    results.append(("User Entities", check_user_entities()))
    results.append(("Timestamp Distribution", check_timestamp_distribution()))

    # Print summary
    print(f"\n{Colors.BLUE}")
    print("=" * 70)
    print("   Summary")
    print("=" * 70)
    print(f"{Colors.NC}")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = f"{Colors.GREEN}✓ PASS{Colors.NC}" if result else f"{Colors.RED}✗ FAIL{Colors.NC}"
        print(f"{name:30s} {status}")

    print(f"\n{Colors.BLUE}Overall: {passed}/{total} checks passed{Colors.NC}\n")

    # Exit with appropriate code
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()

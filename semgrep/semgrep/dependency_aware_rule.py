from os import getenv
from pathlib import Path
from typing import Dict
from typing import Generator
from typing import List
from typing import Tuple

from dependencyparser.models import PackageManagers
from dependencyparser.package_restrictions import dependencies_range_match_any
from dependencyparser.package_restrictions import find_and_parse_lockfiles
from dependencyparser.package_restrictions import ProjectDependsOnEntry

from semgrep.error import SemgrepError
from semgrep.rule import Rule
from semgrep.rule_match import CoreLocation
from semgrep.rule_match import RuleMatch


PACKAGE_MANAGER_MAP = {
    "pypi": PackageManagers.PYPI,
    "npm": PackageManagers.NPM,
    "gem": PackageManagers.GEM,
    "gomod": PackageManagers.GOMOD,
    "cargo": PackageManagers.CARGO,
    "maven": PackageManagers.MAVEN,
}


def parse_depends_on_yaml(
    entries: List[Dict[str, str]]
) -> Generator[ProjectDependsOnEntry, None, None]:
    """
    Convert the entries in the Yaml to ProjectDependsOnEntry objects that specify
    namespace, package name, and semver ranges
    """
    for entry in entries:
        # schema checks should gaurantee we have these fields, but we'll code defensively
        namespace = entry.get("namespace")
        if namespace is None:
            raise SemgrepError(f"project-depends-on is missing `namespace`")
        pm = PACKAGE_MANAGER_MAP.get(namespace)
        if pm is None:
            raise SemgrepError(
                f"unknown package namespace: {namespace}, only {list(PACKAGE_MANAGER_MAP.keys())} are supported"
            )
        package_name = entry.get("package")
        if package_name is None:
            raise SemgrepError(f"project-depends-on is missing `package`")
        semver_range = entry.get("version")
        if semver_range is None:
            raise SemgrepError(f"project-depends-on is missing `version`")
        yield ProjectDependsOnEntry(
            namespace=pm, package_name=package_name, semver_range=semver_range
        )


def run_dependency_aware_rule(
    matches: List[RuleMatch],
    rule: Rule,
    targets: List[Path],
) -> Tuple[List[RuleMatch], List[SemgrepError]]:
    """
    Run a dependency aware rule. These rules filters the results based on the precense or absence
    of dependencies. Dependencies are determined by searching for lockfiles under the first entry
    in the `targets` argument.
    """

    # TODO fix this; associate targets to the lockfiles that they actually use, and remove the env var logic below
    top_level_target_rooted = list(targets[0].parents)
    top_level_target: Path = (
        targets[0] if len(top_level_target_rooted) == 0 else top_level_target_rooted[-1]
    )

    lockfile_target = Path(getenv("SEMGREP_LOCKFILE_PATH", top_level_target))

    dependencies: List[Dict[str, str]] = rule.project_depends_on or []
    dep_rule_errors: List[SemgrepError] = []

    if len(dependencies) == 0:
        # no dependencies to process, so skip
        return matches, []

    dummy_match = RuleMatch(
        rule_id=rule.id,
        message=rule.message,
        metadata=rule.metadata,
        severity=rule.severity,
        path=top_level_target,  # TODO: this should probably be the offending lockfile
        fix=None,
        fix_regex=None,
        start=CoreLocation(0, 0, 0),
        end=CoreLocation(0, 0, 0),
        extra={},
    )

    try:
        depends_on_entries = list(parse_depends_on_yaml(dependencies))
        output = list(
            dependencies_range_match_any(
                depends_on_entries, find_and_parse_lockfiles(lockfile_target)
            )
        )
        output_for_json = [
            {
                "dependency_pattern": vars(dep_pat),
                "found_dependency": vars(found_dep),
                "lockfile": lockfile.name,
            }
            for dep_pat, found_dep, lockfile in output
        ]
        # Dependency checks found nothing, so rule should not match
        if output == []:
            final_matches = []

        # Dependency checks found something, so rule should match
        # and we should get a dummy match indicating the dependency match
        else:
            if matches == []:
                dummy_match.extra["dependency_match_only"] = True
                dummy_match.extra["dependency_matches"] = output_for_json
                matches.append(dummy_match)
            else:
                for match in matches:
                    match.extra["dependency_match_only"] = False
                    match.extra["dependency_matches"] = output_for_json

            final_matches = matches

        return final_matches, dep_rule_errors

    except SemgrepError as e:
        return [], [e]

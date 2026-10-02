"""Install the free Argos Translate model for English to Chinese."""

from __future__ import annotations

from collections import deque

import argostranslate.package


def shortest_package_route(packages, source: str, target: str):
    queue = deque([(source, [])])
    visited = {source}
    while queue:
        code, route = queue.popleft()
        for package in packages:
            if package.from_code != code or package.to_code in visited:
                continue
            next_route = [*route, package]
            if package.to_code == target:
                return next_route
            visited.add(package.to_code)
            queue.append((package.to_code, next_route))
    return []


def main() -> int:
    print("Loading the free Argos model catalogue…")
    argostranslate.package.update_package_index()
    packages = argostranslate.package.get_available_packages()
    selected = {}
    route = shortest_package_route(packages, "en", "zh")
    if not route:
        raise RuntimeError("No downloadable Argos route found for en → zh.")
    for package in route:
        selected[(package.from_code, package.to_code)] = package

    for (source, target), package in selected.items():
        print(f"Installing free offline model {source} → {target}…")
        package_path = package.download()
        argostranslate.package.install_from_path(package_path)

    print("English to Chinese offline model is installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

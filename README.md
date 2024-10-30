nvcheck
=======

1. `env GH_TOKEN=(gh auth token) hatch run python -m nvcheck`
2. merge PR
3. `git pull`
4. `hatch run pkg-push $changed_package`

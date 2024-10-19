nvcheck
=======

1. `hatch run pkg-add python-foobar`
2. add entry in `nvchecker.toml` and commit
3. `env GH_TOKEN=(gh auth token) hatch run python -m nvcheck`
4. merge PR
5. git pull
6. `hatch run pkg-push python-foobar`

# small helper to launch the test with debugpy enabled, allowing you to attach a VS Code debugger to the test run
# See the "Debug Tests" launch configuration in .vscode/launch.json

# e.g.  scripts/debug_tests.sh ami.jobs.test_tasks --keepdb
docker compose run --rm -p 5680:5680 django \
  python -m debugpy --listen 0.0.0.0:5680 --wait-for-client \
  manage.py test $*

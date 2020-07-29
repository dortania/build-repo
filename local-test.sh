pip3 install hammock python-dateutil datetime termcolor purl python-magic
rm -Rf Config Temp Builds
git clone https://github.com/dhinakg/ktextrepo-beta.git Config --depth 1 --single-branch --branch builds --sparse --filter=blob:none
python3 -u check_ratelimit.py
python3 -u updater.py
python3 -u check_ratelimit.py
python3 -u update_config.py
pip3 install hammock python-dateutil datetime termcolor purl python-magic
rm -Rf config.json last_updated.txt Push Temp Builds
git clone https://github.com/dhinakg/ktextrepo-beta.git Push --depth 1 --single-branch --branch builds --sparse --filter=blob:none
cp Push/config.json .
cp Push/last_updated.txt .
python3 -u check_ratelimit.py
python3 -u updater.py
python3 -u check_ratelimit.py
python3 -u update_config.py
mv config.json Push
mv last_updated.txt Push
ls Push
cd Push
git add config.json last_updated.txt
git commit -m "Deploying to builds"
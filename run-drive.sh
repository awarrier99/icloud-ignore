. ./venv/bin/activate
filename=$(realpath ~/Documents)
log_filename=$(echo $filename | sed "s/\//-/g")
nohup python main.py $filename >> icloud-ignore$log_filename.log &
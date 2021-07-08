. ./venv/bin/activate
filename=$(realpath $1)
log_filename=$(echo $filename | sed "s/\//-/g")
python main.py $filename >> icloud-ignore$log_filename.log
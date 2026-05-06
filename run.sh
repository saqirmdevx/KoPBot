if [[ $(screen -ls | grep KoPBot) ]]; then
    echo "KoPBot is running..."
else
    screen -d -m -S KoPBot python3 main.py >> errors.log
fi




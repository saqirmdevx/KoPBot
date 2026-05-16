if [[ $(screen -ls | grep KoPBot) ]]; then
    echo "KoPBot is running..."
else
    # Keep legacy startup output bounded. The bot also writes rotating logs to kopbot.log.
    if [[ -f errors.log && $(wc -c < errors.log) -gt 10485760 ]]; then
        mv errors.log errors.log.1
    fi
    screen -d -m -S KoPBot bash -c 'python3 main.py >> errors.log 2>&1'
fi




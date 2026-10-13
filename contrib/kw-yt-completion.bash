# Bash-completion для kw-yt (v0.2 Волна 4).
# Установка: source contrib/kw-yt-completion.bash
# или: cp contrib/kw-yt-completion.bash ~/.local/share/bash-completion/completions/kw-yt
_kw_yt() {
    local cur prev sub
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    sub="${COMP_WORDS[1]}"

    case "$prev" in
        --format)
            COMPREPLY=( $(compgen -W "srt vtt json txt md jsonl csv all" -- "$cur") )
            return 0
            ;;
        --langs|--whisper-model|--jobs|-j|--out|-o|--from-file|--in|--context|--limit|--port)
            return 0
            ;;
    esac

    case "$sub" in
        search)
            COMPREPLY=( $(compgen -W "--in --context --limit" -- "$cur") )
            return 0
            ;;
        export)
            COMPREPLY=( $(compgen -W "--in --format --out --summary --no-summary" -- "$cur") )
            return 0
            ;;
        serve)
            COMPREPLY=( $(compgen -W "--port" -- "$cur") )
            return 0
            ;;
        "")
            COMPREPLY=( $(compgen -W "search serve export --from-file --out --langs --format --no-fallback-whisper --whisper-model --jobs --resume --version" -- "$cur") )
            return 0
            ;;
    esac

    COMPREPLY=( $(compgen -W "--from-file --out --langs --format --no-fallback-whisper --whisper-model --jobs --resume --version" -- "$cur") )
    return 0
}
complete -F _kw_yt kw-yt

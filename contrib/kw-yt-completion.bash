# Bash-completion для kw-yt. Сгенерировано `kw-yt completion bash` — не править вручную.
# Установка: eval "$(kw-yt completion bash)"
# или: kw-yt completion bash > ~/.local/share/bash-completion/completions/kw-yt
_kw_yt() {
    local cur prev sub
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    sub="${COMP_WORDS[1]}"

    case "$prev" in
        --format)
            case "$sub" in
                export) COMPREPLY=( $(compgen -W "csv jsonl" -- "$cur") ); return 0 ;;
                *) COMPREPLY=( $(compgen -W "all csv json jsonl md srt txt vtt" -- "$cur") ); return 0 ;;
            esac
            ;;
        --color)
            COMPREPLY=( $(compgen -W "always auto never" -- "$cur") )
            return 0
            ;;
        --context|--from|--from-file|--host|--in|--jobs|--langs|--limit|--older-than|--out|--port|--summary|--to|--whisper-model|-j|-o)
            return 0
            ;;
    esac

    case "$sub" in
        clean)
            COMPREPLY=( $(compgen -W "--all --cache --color --help --no-color --older-than --yes -h" -- "$cur") )
            return 0
            ;;
        completion)
            COMPREPLY=( $(compgen -W "bash" -- "$cur") )
            return 0
            ;;
        export)
            COMPREPLY=( $(compgen -W "--color --format --help --in --no-color --no-summary --out --summary -h" -- "$cur") )
            return 0
            ;;
        library)
            COMPREPLY=( $(compgen -W "--color --help --json --no-color -h" -- "$cur") )
            return 0
            ;;
        search)
            COMPREPLY=( $(compgen -W "--color --context --help --in --limit --no-color -h" -- "$cur") )
            return 0
            ;;
        serve)
            COMPREPLY=( $(compgen -W "--color --help --host --no-color --port -h" -- "$cur") )
            return 0
            ;;
        stats)
            COMPREPLY=( $(compgen -W "--color --help --in --json --no-color -h" -- "$cur") )
            return 0
            ;;
        "")
            COMPREPLY=( $(compgen -W "--color --format --from --from-file --help --jobs --langs --no-color --no-fallback-whisper --out --resume --to --version --whisper-model -h -j -o clean completion export library search serve stats" -- "$cur") )
            return 0
            ;;
    esac

    COMPREPLY=( $(compgen -W "--color --format --from --from-file --help --jobs --langs --no-color --no-fallback-whisper --out --resume --to --version --whisper-model -h -j -o" -- "$cur") )
    return 0
}
complete -F _kw_yt kw-yt

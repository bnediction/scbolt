count_genes_in_file() {
    local file="$1"

    if [[ -z "$file" ]]; then
        echo "Usage: count_genes_in_file <fichier>"
        return 1
    fi

    if [[ ! -f "$file" ]]; then
        echo "Fichier introuvable : $file"
        return 1
    fi

    local genes=(
        Tal1 Notch1 Meis1 Pbx1 Hhex Cd34
        Cdk6 Gata2 Fli1 Gfi1b Epor Nfe2l2 Vwf Tfrc Hemgn
        Elane Gfi1 Irf8 Spi1 Csf1 Ctsg
        Csf3r Ets1 Mef2c
        Gata1 Gata3 Tgfbr2 Etv6 Stat3
    )

    local found=0
    local total=${#genes[@]}

    for gene in "${genes[@]}"; do
        if grep -iwq "$gene" "$file"; then
            echo "$gene: present"
            ((found++))
        else
            echo "$gene: absent"
        fi
    done

    echo
    echo "Total: $found / $total gènes trouvés"
}
RED='\033[1;31m'
YELLOW='\033[1;33m'
GREEN='\033[1;32m'
CODE='\033[1;30;43m'
NC='\033[0m'

# Install conda environments
echo -e "${YELLOW}installing development environment${NC}"
conda env create -f requirements/environment.yml
echo -e "${YELLOW}activate with ${CODE} conda activate data-lunch ${NC}\n"

echo -e "${YELLOW}installing ci-cd environment${NC}"
conda env create -f requirements/ci-cd.yml
echo -e "${YELLOW}activate with ${CODE} conda activate ci-cd ${NC}\n"

echo -e "${YELLOW}installing google cloud environment${NC}"
conda env create -f requirements/gc-sdk.yml
echo -e "${YELLOW}activate with ${CODE} conda activate gc-sdk ${NC}\n"

echo -e "${GREEN}environments installed${NC}\n"

# Setup GCP SDK
while true; do
    echo -e "${YELLOW}setup google cloud SDK? [y/n]${NC}"
    read yn
    case $yn in
        [Yy]*)  conda activate gc-sdk ; make gcp-config ; conda deactivate ; echo -e "\n${GREEN}GCP SDK configured${NC}\n" ; break ;;  
        [Nn]*) echo "\n${RED}GCP SDK not configured${NC}\n" ; break ;;
    esac
done

# Install pre-commit hooks
echo -e "${YELLOW}installing pre-commit environment${NC}"
conda activate ci-cd
pre-commit install
echo -e "\n${GREEN}pre-commit hooks installed${NC}\n"
while true; do
    echo -e "${YELLOW}autoupdate pre-commit hooks? [y/n]${NC}"
    read yn
    case $yn in
        [Yy]*)  pre-commit autoupdate ; echo -e "\n${GREEN}pre-commit hooks updated${NC}\n" ; break ;;  
        [Nn]*) echo "\n${RED}pre-commit hooks not updated${NC}\n" ; break ;;
    esac
done
conda deactivate

# Activate dev env and install CLI
while true; do
    echo -e "${YELLOW}activate development environment? [y/n]${NC}"
    read yn
    case $yn in
        [Yy]*)  conda activate data-lunch ;
        echo -e "\n${GREEN}environment activated${NC}\n" ;
        echo -e "${YELLOW}install command line interface? [y/n]${NC}";
        read yn;
        while true; do
            case $yn in
                [Yy]*)  set -e ; pip install --no-deps -e \. && echo -e "${YELLOW}use with ${CODE} data-lunch --help ${NC}\n" ; set +e ; echo -e "${GREEN}CLI installedd${NC}\n" ; break ;;
                [Nn]*) echo "\n${RED}CLI not installed${NC}\n" ; break ;;
            esac
        done
        break ;;  
        [Nn]*) echo "\n${RED}environment not activated${NC}\n" ; break ;;
    esac
done

echo -e "${GREEN}done${NC}\n"

return 0
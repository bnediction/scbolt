# retinoic acid resistance leukemias


## Add your files

- [ ] [Create](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#create-a-file) or [upload](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#upload-a-file) files
- [ ] [Add files using the command line](https://docs.gitlab.com/ee/gitlab-basics/add-file.html#add-a-file-using-the-command-line) or push an existing Git repository with the following command:

```
cd existing_repo
git remote add origin https://gitub.u-bordeaux.fr/troncalli/retinoic-acid-resistance-leukemias.git
git branch -M main
git push -uf origin main
```

## Description
Let people know what your project can do specifically. Provide context and add a link to any reference visitors might be unfamiliar with. A list of Features or a Background subsection can also be added here. If there are alternatives to your project, this is a good place to list differentiating factors.

# Installation

## Using *Bash*

Setup prerequisites must be verified:
1. verify that *latex* markup language is already installed. If not, please use:
```sh
apt-get install texlive dvipng texlive-latex-extra texlive-fonts-recommended
```
2. verify that *Anaconda* package manager is already installed. If not, please install and download it [here](https://www.anaconda.com/download/). Then please use:
```bash
conda config --add channels bioconda
conda config --add channels conda-forge
```

Download and configure project:
```sh
git clone https://gitub.u-bordeaux.fr/troncalli/retinoic-acid-resistance-leukemias.git leukemia
cd leukemia
bash config/env_installation.sh
```
Run the pipeline:
```bash
bash workflow.sh
```

## Authors and acknowledgment
Show your appreciation to those who have contributed to the project.

## License
For open source projects, say how it is licensed.

## Project status
Ongoing project

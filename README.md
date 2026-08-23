# MLOps Course Repository

Course repository for class exercises and projects.

Environment: **Rocky Linux 9.8 (Blue Onyx)**.

## Class collaboration

Use a fork, a branch, and a Pull Request. Do not edit `main` directly.

After cloning your fork:

```bash
git remote add upstream https://github.com/Jesteban247/mlops-course-repo.git
git switch main
git pull upstream main
git switch -c your-branch-name
```

After making changes:

```bash
git status
git add .
git commit -m "Describe your changes"
git push -u origin your-branch-name
```

Use [Gitmoji](https://gitmoji.dev) in commit messages to clearly describe the purpose of each change. For example:

```bash
git commit -m "📝 update README with collaboration guidelines"
```

On GitHub, open a Pull Request from your branch into `main`. The repository owner reviews and merges it.

After the Pull Request is merged:

```bash
git switch main
git pull upstream main
git push origin main
```

Useful commands:

```bash
git branch
git branch -a
git log --oneline -5
git diff
git remote -v
```

Do not commit passwords, tokens, private keys, or other secrets.

## Conda

Install Miniconda:

```bash
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
source ~/.bashrc
```

## Docker

Install Docker on Rocky Linux:

```bash
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
sudo dnf -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker
```

Check Docker:

```bash
docker --version
docker compose version
docker run hello-world
docker ps
docker ps -a
docker images
```

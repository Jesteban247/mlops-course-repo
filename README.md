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

## Python environment with uv

Install `uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
```

For a new assignment, run this once:

```bash
cd assignment_N
uv init --bare
uv python pin 3.14
uv add PACKAGE_NAME
uv sync
```

Replace `assignment_N` with the assignment directory and `PACKAGE_NAME` with each dependency it needs. For an assignment that already has `pyproject.toml` and `uv.lock`, setup is simply:

```bash
cd assignment_N
uv sync
```

`uv sync` creates `.venv` automatically. Run Python files from the assignment directory with `uv run`:

```bash
uv run train.py
uv run inference.py
uv run uvicorn api:app --host 0.0.0.0 --port 8989
```

Use `uv add PACKAGE_NAME` or `uv remove PACKAGE_NAME` when changing dependencies. These commands update `pyproject.toml` and `uv.lock`.

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

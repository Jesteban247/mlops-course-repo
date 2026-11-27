# Project 3 — Notebooks on NBAM07

Command to set up the virtual environment and install the required packages for Project 3 on NBAM07:

```bash
cd /home/estudiante/mlops-course-repo/project_3 &&
uv venv --clear --python 3.14 --prompt project-3-nbam07 .venv &&
uv pip install --python .venv/bin/python -r notebooks/requirements.txt &&
.venv/bin/python -m ipykernel install --user --name project-3-nbam07 \
  --display-name "Project 3 (Python 3.14 on NBAM07)"
```


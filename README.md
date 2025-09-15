# cpu_scheduler
master thesis project
# TLAS: Tail Latency Alleviate Scheduler for Serverless Systems

This repository contains the implementation and evaluation framework for **TLAS**,  
a real-time, adaptive CPU scheduler designed to mitigate **tail latency** in serverless environments.  

TLAS integrates into the existing **SFS scheduler** framework, introducing:
- **Dynamic priority adjustment** for straggling requests
- **Online SLO estimation** based on rolling statistics
- **Two-level queue design** with FIFO + CFS integration
- **Low-overhead monitoring** for real-time scheduling

## 🌟 Key Features
- Reduces **P99/P99.9 latency** by 3× compared to SFS
- Alleviates starvation for long-running tasks
- Robust across diverse workloads and CPU load levels
- Dockerized for easy deployment on CloudLab servers

## 📂 Project Structure
- `src/` – Go source code (TLAS, SFS, STCF implementations)
- `workloads/` – Workload traces and generation scripts
- `evaluation/` – Experiment scripts and visualization
- `docker/` – Dockerfiles and deployment instructions
- `docs/` – Architecture diagrams and paper materials

## 🚀 Quick Start
```bash
# Clone repository
git clone https://github.com/yourusername/TLAS.git
cd TLAS

# Build and run with Go
cd src
go run main.go -p tla -t test2 -n 12 > ../evaluation/results/tla.txt

# Offline DataMate pipeline_llm image for 2 x RTX 5090 (Blackwell / sm_120).
# Compliant with Zalo AI Challenge 2026 Docker Guide:
#   docker run --rm --gpus '"device=0,1"' --network none --shm-size=16g \
#     --entrypoint bash -v /path/to/test:/data:ro -v /path/to/output:/result \
#     zaic2026_datamate_<team_name>:final /code/predict.sh

ARG VLLM_IMAGE=vllm/vllm-openai:v0.32.0
FROM ${VLLM_IMAGE}

ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    VLLM_NO_USAGE_STATS=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    DATAMATE_PROJECT_ROOT=/app \
    DATAMATE_SYSTEM=pipeline_llm \
    VLLM_USE_FLASHINFER_SAMPLER=0 \
    LLM_BASE_URL=http://127.0.0.1:8000/v1 \
    LLM_MODEL=qwen3-14b \
    LLM_API_KEY=EMPTY \
    LLM_DISABLE_THINKING=true

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY src /app/src
COPY evals /app/evals
COPY rules /app/rules
# train/ is gitignored (organizer data); the pipeline reads /data/rulebook.md at run time.
RUN mkdir -p /app/train

RUN python3 -m pip install --no-cache-dir . \
    && python3 -c "import duckdb, python_calamine, vllm; from datamate.config import PROJECT_ROOT as R; assert (R / 'rules' / 'train.json').is_file(), R; print('ok', vllm.__version__, R)"

# Weights downloaded by docker/fetch_model.sh (not in git).
COPY docker/models /models
COPY docker/predict.sh /app/docker/predict.sh
COPY docker/make_manifest.py docker/manifest_meta.json /app/docker/
COPY docker/CODE_README.md /code/README.md
COPY docker/TRAINING_README.md /code/training_code/README.md
# Organizer train split, when build_vm.sh fetched it (TRAIN_URL); otherwise only .gitkeep.
COPY docker/train_data /code/training_code/train
RUN cp -r /app/src /app/rules /app/evals /app/pyproject.toml /code/training_code/ \
    && python3 /app/docker/make_manifest.py /code/training_code /code/training_code/data_manifest.json \
       /app/docker/manifest_meta.json \
    && cp /app/docker/predict.sh /code/predict.sh \
    && chmod +x /app/docker/predict.sh /code/predict.sh

ENTRYPOINT []
CMD ["/code/predict.sh"]

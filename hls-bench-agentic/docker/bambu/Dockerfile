FROM bambuhls/bambu:latest

WORKDIR /workspace

SHELL ["/bin/bash", "-lc"]

CMD ["bash", "-lc", "bash tests/run_csim.sh && bash tests/run_synth.sh && bash tests/run_cosim.sh && bash tests/run_rtl_security.sh"]

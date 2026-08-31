# Thin wrapper around ./run — see `./run help`
.PHONY: bootstrap setup dev doctor test stop clean

bootstrap: ; @./run bootstrap
setup:     ; @./run setup
dev:       ; @./run dev
doctor:    ; @./run doctor
test:      ; @./run test
stop:      ; @./run stop
clean:     ; @./run clean

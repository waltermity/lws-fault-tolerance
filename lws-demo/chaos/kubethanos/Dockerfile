# kubethanos (github.com/berkay-dincer/kubethanos) has no published image and its
# upstream Dockerfile cannot be used as-is: it runs `go run main.go` during the build
# (which needs a live cluster) and hard-codes GOARCH=amd64
# This Dockerfile builds the same pinned source for the host's architecture.
FROM golang:1.13-alpine AS build
RUN apk add --no-cache git
ARG KUBETHANOS_COMMIT=e3f8f07aa9ed9fd3281ed436165fd5dd6ab36e07
RUN git clone https://github.com/berkay-dincer/kubethanos.git /src \
 && cd /src && git checkout "$KUBETHANOS_COMMIT"
WORKDIR /src
# Patch: after deleting a pod, kubethanos records an Event via reference.GetReference(),
# which needs metadata.selfLink. The API server stopped filling selfLink in K8s 1.20, so on
# modern clusters every kill logs "selfLink was empty" (the pod IS deleted). Build the
# ObjectReference by hand so the "killed by kubethanos" Event works again.
RUN sed -i \
      -e 's|ref, err := reference.GetReference(scheme.Scheme, &pod)|ref, err := \&v1.ObjectReference{Kind: "Pod", APIVersion: "v1", Namespace: pod.Namespace, Name: pod.Name, UID: pod.UID}, error(nil)|' \
      -e '/"k8s.io\/client-go\/tools\/reference"/d' \
      kubethanos/kubethanos.go \
 && grep -q 'ObjectReference{Kind: "Pod"' kubethanos/kubethanos.go
ENV CGO_ENABLED=0 GO111MODULE=on
RUN go build -o /bin/kubethanos -ldflags "-w -s" .

FROM alpine:3.20
RUN apk add --no-cache ca-certificates
COPY --from=build /bin/kubethanos /bin/kubethanos
USER 65534
ENTRYPOINT ["/bin/kubethanos"]

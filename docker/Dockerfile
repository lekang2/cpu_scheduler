FROM ubuntu:20.04
RUN apt update -y && apt install schedtool software-properties-common -y && add-apt-repository ppa:longsleep/golang-backports && apt update -y && apt install golang-go python python3 -y
#RUN apt update -y && apt install schedtool golang-go python python3 -y
RUN mkdir /SFS-standalone
# Copy only the xxx_xxx folder
#COPY ./SFS-standalone/0322_workload /SFS-standalone/0322_workload
COPY ./SFS-standalone/* /SFS-standalone/
WORKDIR /SFS-standalone
RUN go build && mkdir /result
CMD ["/bin/bash"]
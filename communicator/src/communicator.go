package main

import (
	"bufio"
	"bytes"
	"encoding/binary"
	"fmt"
	"math/rand"
	"net"
	"os"
	"os/exec"
	"regexp"
	"strconv"
	"strings"
)

// Changing CONNECTION_TYPE is not recommended

const (
	DEFAULT_HOST     = "0.0.0.0"
	DEFAULT_PORT     = "1919"
	CONNECTION_TYPE  = "tcp"
	NUM_PORT_RETRIES = 5
)

var BUFFER_LEN = 5120

func main() {
	arguments := os.Args[1:]
	listen_port := DEFAULT_PORT
	argslen := len(arguments)
	if argslen == 0 {
		fmt.Println("Either -s or -c option needed. Use -h for help.")
		gracefulExit()
	} else if argslen > 1 {
		listen_port = arguments[1]
	}
	if arguments[0] == "-s" {
		loop := 0
		server, err := net.Listen(CONNECTION_TYPE, DEFAULT_HOST+":"+listen_port)
		for err != nil && loop < NUM_PORT_RETRIES && argslen <= 1 {
			listen_port = strconv.Itoa(rand.Intn(40000-2000) + 2000)
			server, err = net.Listen(CONNECTION_TYPE, DEFAULT_HOST+":"+listen_port)
			loop++
		}
		if err != nil {
			fmt.Println("Error listening: ", err.Error())
			os.Exit(1)
		}
		defer server.Close()
		fmt.Println("Listening on " + DEFAULT_HOST + ":" + listen_port)
		for {
			client, err := server.Accept()
			if err != nil {
				fmt.Println("Error accepting: ", err.Error())
				os.Exit(1)
			}
			handleRequest(client)
		}
	} else if arguments[0] == "-c" {
		client, err := net.Dial(CONNECTION_TYPE, DEFAULT_HOST+":"+listen_port)
		if err != nil {
			fmt.Println("Couldn't connect to server")
			gracefulExit()
		}
		defer client.Close()
		reader := bufio.NewReaderSize(os.Stdin, BUFFER_LEN)
		command, err := reader.ReadString('\n')
		if err != nil {
			clientClose(err, client)
			gracefulExit()
		}
		command = strings.Trim(command, "\n")
		commandLen := len(command)
		lenBuffer := make([]byte, 8)
		buffer := make([]byte, BUFFER_LEN)
		binary.BigEndian.PutUint64(lenBuffer, uint64(commandLen))
		sent := 0
		for sent < len(lenBuffer) {
			wrote, err := client.Write(lenBuffer)
			if err != nil {
				clientClose(err, client)
				gracefulExit()
			}
			sent += wrote
		}
		sent = 0
		for sent < commandLen {
			copy(buffer, command)
			sendBuffer := bytes.Trim(buffer, "\x00")
			wrote, err := client.Write(sendBuffer)
			if err != nil {
				clientClose(err, client)
				gracefulExit()
			}
			sent += wrote
		}
		received := 0
		for received < len(lenBuffer) {
			read, err := client.Read(lenBuffer)
			if err != nil {
				clientClose(err, client)
				gracefulExit()
			}
			received += read
		}
		outputLen := binary.BigEndian.Uint64(lenBuffer)
		received = 0
		for index, _ := range buffer {
			buffer[index] = 0
		}
		var output strings.Builder
		for received < int(outputLen) {
			read, err := client.Read(buffer)
			if err != nil {
				clientClose(err, client)
				gracefulExit()
			}
			recievedBuffer := bytes.Trim(buffer, "\x00")
			output.Write(recievedBuffer)
			received += read
		}
		fmt.Print(output.String())
	} else if arguments[0] == "-h" {
		fmt.Println("Usage: communicator [OPTION] [PORT]")
		fmt.Println("Options:")
		fmt.Println("  -s\t\tStart server")
		fmt.Println("  -c\t\tStart client")
		fmt.Println("  -h\t\tShow help")
		fmt.Println("PORT is optional and defaults to 1919 for server use.")
	} else {
		fmt.Println("Invalid option")
		gracefulExit()
	}
}

func clientClose(err error, client net.Conn) {
	fmt.Println("Encountered an error: ")
	fmt.Println(err.Error())
	client.Close()
}

func gracefulExit() {
	fmt.Println("Exiting...")
	os.Exit(1)
}

func handleRequest(client net.Conn) {
	lenBuffer := make([]byte, 8)
	buffer := make([]byte, BUFFER_LEN)
	received := 0
	flag := 0
	for received < len(lenBuffer) && received < BUFFER_LEN {
		read, err := client.Read(lenBuffer[received:])
		if err != nil {
			clientClose(err, client)
			flag = 1
			break
		}
		received += read
	}
	if flag == 1 {
		return
	}
	commandLen := binary.BigEndian.Uint64(lenBuffer)
	flag = 0
	received = 0
	var output strings.Builder
	for received < int(commandLen) {
		read, err := client.Read(buffer[received:])
		if err != nil {
			clientClose(err, client)
			flag = 1
			break
		}
		recievedBuffer := bytes.Trim(buffer[received:], "\x00")
		output.Write(recievedBuffer)
		received += read
	}
	if flag == 1 {
		return
	}
	outputStr := output.String()
	fmt.Println("Running Command: ", outputStr)
	allCommands := strings.Split(outputStr, "|")
	match := regexp.MustCompile(`[^\s"']+|"([^"]*)"|'([^']*)'`)
	var err error
	var errOut strings.Builder
	var out strings.Builder
	var lastOutput strings.Builder
	for _, element := range allCommands {
		element = strings.Trim(element, " ")
		arguments := match.FindAllString(element, -1)
		for i, argument := range arguments {
			arguments[i] = strings.Trim(argument, "'\"")
		}
		if len(arguments) > 0 {
			command := exec.Command(string(arguments[0]), arguments[1:]...)
			input, err := command.StdinPipe()
			if err != nil {
				fmt.Println(err.Error())
				input.Close()
				break
			}
			defer input.Close()
			command.Stdout = &out
			command.Stderr = &errOut
			command.Stdin = strings.NewReader(lastOutput.String())
			err = command.Run()
			if err != nil {
				lastOutput.WriteString("Error Occured: \n")
				lastOutput.WriteString(err.Error())
				lastOutput.WriteString("\n\nStderr of program (if any): \n")
				lastOutput.WriteString(errOut.String())
				break
			}
		}
		lastOutput.Reset()
		_, err = lastOutput.WriteString(out.String())
		if err != nil {
			fmt.Println("Error reading command output: ", err.Error())
			break
		}
		out.Reset()
		errOut.Reset()
	}
	binary.BigEndian.PutUint64(lenBuffer, uint64(len(lastOutput.String())))
	sent := 0
	for sent < len(lenBuffer) {
		wrote, err := client.Write(lenBuffer[sent:])
		if err != nil {
			clientClose(err, client)
			flag = 1
			break
		}
		sent += wrote
	}
	if flag == 1 {
		return
	}
	sent = 0
	for sent < len(lastOutput.String()) && sent < BUFFER_LEN {
		wrote, err := client.Write(([]byte(lastOutput.String()))[sent:])
		if err != nil {
			clientClose(err, client)
			flag = 1
			break
		}
		sent += wrote
	}
	if flag == 1 {
		return
	}
	client.Close()
}

///usr/bin/env [ "$JAVA_HOME" ] && JAVA_EXE="$JAVA_HOME/bin/java" || { type -p java >/dev/null 2>&1 && JAVA_EXE=$(type -p java) || { [ -x "/usr/bin/java" ] && JAVA_EXE="/usr/bin/java" || { echo "Unable to find Java"; exit 1; } } }; "$JAVA_EXE" "${JVM_OPTS[@]}" "$0" "$@"; exit $?
/**
 * notification-server
 * Copyright (C) 2024
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */
import static java.lang.Integer.parseInt;
import static java.lang.Runtime.getRuntime;
import static java.lang.String.format;
import static java.lang.System.arraycopy;
import static java.lang.System.exit;
import static java.lang.System.in;
import static java.lang.System.out;
import static java.util.Arrays.asList;
import static java.util.logging.LogManager.getLogManager;

import java.io.BufferedReader;
import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.ServerSocket;
import java.net.Socket;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ConcurrentSkipListSet;
import java.util.function.BiConsumer;
import java.util.function.Consumer;
import java.util.logging.Logger;

public class Main {

  private static final String version = "1.4.1";

  private static String logFormat = "%1$tF %1$tT | %5$s%n";
  static {
    try {
      var logConfig = """
          handlers=java.util.logging.ConsoleHandler
          java.util.logging.SimpleFormatter.format=%s
          """.formatted(logFormat);
      getLogManager().readConfiguration(new ByteArrayInputStream(logConfig.getBytes()));
    }
    catch (IOException e) {
      e.printStackTrace();
    }
  }
  private static final Logger LOG = Logger.getGlobal();

  public static void main(String[] args) {
    var arguments = Arguments.parse(args);
    if (arguments.displayHelp()) {
      Arguments.printUsage();
      return;
    }
    if (arguments.displayVersion()) {
      out.println(version);
      return;
    }

    getRuntime().addShutdownHook(
        new Thread(() -> out.format(logFormat, LocalDateTime.now(), null, null, null, "Shutting down")));

    var server = new NotificationServer(arguments.port());
    server.start();

    var deleteClient = new QuestionCommand('d', "delete client", "Client to delete (enter port number)? ", answer -> {
      try {
        var port = parseInt(answer);
        server.deleteClient(port);
      }
      catch (NumberFormatException e) {
        out.println("Invalid port number");
      }
    });
    var printClients = new BasicCommand('p', "print clients", server::printClientNames);
    var quit = new BasicCommand('q', "quit", () -> exit(0));
    var commandHandler = new CommandHandler(deleteClient, printClients, quit);
    char helpKey = 'h';
    commandHandler.addHelpCommand(helpKey);
    LOG.info(format("Press %s to see a list of available keyboard commands", helpKey));
    commandHandler.start();
  }

}

record Arguments(int port, boolean displayHelp, boolean displayVersion) {

  private static final Logger LOG = Logger.getGlobal();

  public static Arguments parse(String[] args) {
    int port = 19725;
    boolean displayHelp = false;
    boolean displayVersion = false;
    for (int i = 0; i < args.length; i++) {
      switch (args[i]) {
        case "-p" -> port = parseInt(args[++i]);
        case "-h" -> displayHelp = true;
        case "-v" -> displayVersion = true;
        default -> LOG.info(format("Unknown option: %s", args[i]));
      }
    }
    return new Arguments(port, displayHelp, displayVersion);
  }

  public static void printUsage() {
    out.print("""
        Usage: notification-server [-p port] [-h] [-v]
            -p Port to listen on. Default = 19725
            -v Display version
            -h Display help
        """);
  }
}

class NotificationServer {

  private static final Logger LOG = Logger.getGlobal();
  private int port;

  public NotificationServer(int port) {
    this.port = port;
  }

  private record ClientSocket(Socket socket, String clientName) {

    public int getPort() {
      return socket.getPort();
    }

    public String getClientName() {
      return clientName;
    }

    public OutputStream getOutputStream() throws IOException {
      return socket.getOutputStream();
    }

    public void close() throws IOException {
      socket.close();
    }
  }

  private Set<ClientSocket> clientSockets = new ConcurrentSkipListSet<>(
      (socket1, socket2) -> socket1.getPort() - socket2.getPort());

  private Consumer<ClientSocket> onClientConnect = socket -> {
    try {
      socket.getOutputStream().write(format("%s%n", "connected").getBytes());
    }
    catch (IOException e) {
      LOG.info(format("Error while writing to socket: %s", e.getMessage()));
    }
  };

  private BiConsumer<String, ClientSocket> onClientMessage = (message, fromClientSocket) -> {
    clientSockets.forEach(socket -> {
      try {
        if (socket != fromClientSocket) {
          socket.getOutputStream().write(format("%s%n", message).getBytes());
        }
      }
      catch (IOException e) {
        LOG.info(format("Error while writing to socket: %s", e.getMessage()));
      }
    });
  };

  private Consumer<ClientSocket> onClientDisconnect = socket -> {
    LOG.info(format("Client disconnect: %s (%s)", socket.getPort(), socket.getClientName()));
    clientSockets.remove(socket);
  };

  public void start() {
    new Thread(() -> {
      try (var serverSocket = new ServerSocket(port)) {
        LOG.info(format("Listening on port %d ...", port));
        while (true) {
          var clientSocket = serverSocket.accept();
          startClientThread(clientSocket, onClientConnect, onClientMessage, onClientDisconnect);
        }
      }
      catch (IOException e) {
        LOG.info(e.getMessage());
      }
    }).start();

    getRuntime().addShutdownHook(new Thread(() -> clientSockets.forEach(this::deleteClient)));
  }

  public void deleteClient(int port) {
    clientSockets.stream()
        .filter(cs -> cs.getPort() == port)
        .findFirst()
        .ifPresent(this::deleteClient);
  }

  private void deleteClient(ClientSocket socket) {
    try {
      socket.close();
      clientSockets.remove(socket);
    }
    catch (IOException e) {
      LOG.info(e.getMessage());
    }
  }

  public void printClientNames() {
    clientSockets.forEach(socket -> out.format("%s (%s)%n", socket.getPort(), socket.getClientName()));
  }

  private void startClientThread(Socket socket, Consumer<ClientSocket> onClientConnect,
      BiConsumer<String, ClientSocket> onClientMessage,
      Consumer<ClientSocket> onClientDisconnect) {
    new Thread(() -> {
      try (var reader = new BufferedReader(new InputStreamReader(socket.getInputStream()))) {
        var clientName = reader.readLine();
        var clientSocket = new ClientSocket(socket, clientName);
        clientSockets.add(clientSocket);
        LOG.info(format("Client connect: %s (%s)", clientSocket.getPort(), clientSocket.getClientName()));
        onClientConnect.accept(clientSocket);
        String message;
        while ((message = reader.readLine()) != null) {
          onClientMessage.accept(message, clientSocket);
        }
        onClientDisconnect.accept(clientSocket);
      }
      catch (IOException e) {
        LOG.info(e.getMessage());
      }
    }).start();
  }

}

abstract sealed class Command permits BasicCommand, QuestionCommand {
  private char key;
  private String description;

  public Command(char key, String description) {
    this.key = key;
    this.description = description;
  }

  public char getKey() {
    return key;
  }

  public String getDescription() {
    return description;
  }
}

final class BasicCommand extends Command {
  private Runnable command;

  public BasicCommand(char key, String description, Runnable command) {
    super(key, description);
    this.command = command;
  }

  public Runnable getCommand() {
    return command;
  }
}

final class QuestionCommand extends Command {
  private String question;
  private Consumer<String> command;

  public QuestionCommand(char key, String description, String question, Consumer<String> command) {
    super(key, description);
    this.question = question;
    this.command = command;
  }

  public String getQuestion() {
    return question;
  }

  public Consumer<String> getCommand() {
    return command;
  }
}

class CommandHandler {

  private List<Command> commands = new ArrayList<>();
  private Terminal terminal = new Terminal();

  public CommandHandler(Command... commands) {
    this.commands.addAll(asList(commands));
  }

  public void start() {
    terminal.setCommandMode();
    try {
      int read;
      while ((read = in.read()) != -1) {
        handle(read);
      }
    }
    catch (IOException e) {
      e.printStackTrace();
    }
  }

  public void addHelpCommand(char key) {
    var helpCommand = new BasicCommand(key, "print available commands", this::printCommands);
    this.commands.add(helpCommand);
  }

  private void handle(int read) throws IOException {
    for (var command : commands) {
      if (command.getKey() == read) {
        switch (command) {
          case QuestionCommand qc -> qc.getCommand().accept(askQuestion(qc.getQuestion()));
          case BasicCommand bc -> bc.getCommand().run();
        }
      }
    }
  }

  private String askQuestion(String question) throws IOException {
    out.print(question);
    terminal.restore();
    var answer = new BufferedReader(new InputStreamReader(in)).readLine();
    terminal.setCommandMode();
    return answer;
  }

  private void printCommands() {
    out.println("Available commands:");
    commands.stream()
        .sorted((c1, c2) -> Character.compare(c1.getKey(), c2.getKey()))
        .map(command -> "    %c: %s".formatted(command.getKey(), command.getDescription()))
        .forEach(System.out::println);
  }
}

class Terminal {
  private String originalConfig;

  public Terminal() {
    originalConfig = stty("-g").trim();
    getRuntime().addShutdownHook(new Thread(this::restore));
  }

  public void setCommandMode() {
    stty("-icanon", "min", "1"); // read one character at the time
    stty("-echo"); // no echo
  }

  public void restore() {
    stty(originalConfig);
  }

  private String stty(String... args) {
    var output = "";
    try {
      var command = buildCommand(args);
      var ttyFile = new File("/dev/tty");
      var process = new ProcessBuilder(command).redirectInput(ttyFile).start();
      var inputStream = process.getInputStream();
      output = new String(inputStream.readAllBytes());
      process.waitFor();
    }
    catch (IOException | InterruptedException e) {
      e.printStackTrace();
    }
    return output;
  }

  private String[] buildCommand(String[] args) {
    var command = new String[args.length + 1];
    command[0] = "stty";
    arraycopy(args, 0, command, 1, args.length);
    return command;
  }
}

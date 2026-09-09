from core.router import handle_command


def main():
    print("JARVIS starting...")
    print("System online.")

    while True:
        command = input("\nTu: ")

        if command.lower() in ["esci", "chiudi", "exit"]:
            print("JARVIS: Sistema offline.")
            break

        response = handle_command(command)

        print(f"JARVIS: {response}")


if __name__ == "__main__":
    main()
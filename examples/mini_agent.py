from agent_runtrace import Recorder

rec = Recorder("mini-agent")
rec.log_llm("plan", "Make a plan", "1. Check Python. 2. Run a command. 3. Summarize.", model="demo")
result = rec.run(["python", "-c", "print('hello from an agent tool')"])
rec.log_llm("summary", "Summarize the result", f"The command exited with {result.returncode}.", model="demo")
print(rec.finish())

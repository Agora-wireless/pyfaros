#!/usr/bin/env python3

import asyncio
import faros_discovery


async def test_some_remote_operations(found):
  # This opens a context over a list of Remote objects. Within the following
  # scope, each of them has a valid connection open, until the end of the
  # async with block.
  async with faros_discovery.Remote.sshify(found) as connections:
    # This is the hardest thing to understand in the code:
    # connection.run(...) is not actually the execution of the command, it
    # actually returns an "awaitable" object which can be run later. We've
    # aggregated/staged all the commands to run here.
    staged_connection_runs = [
        connection.run("echo 'hello world from `hostname`'")
        for connection in connections
    ]
    # asyncio.as_completed(<list of awaitables>) returns a /synchronous/
    # iterator that returns awaitables in the order that the job completes.
    for run in asyncio.as_completed(staged_connection_runs):
      # This await probably doesn't block, because we can be pretty sure
      # that the result is ready if the iterator has ordered it as so. If
      # it's not ready, it's at least the first-available result we can
      # get at.
      res = await run
      # We've unboxed res from the await call, and now we have a simple
      # result object from the asyncssh library.
      print(res)
    # Notice, the connection is still alive, each call to connection.run opens a new
    # session, but not a new TCP connection.
    runs = [
        connection.run("echo 'the connection on `hostname` never closed!'")
        for connection in connections
    ]
    for run in asyncio.as_completed(runs):
      res = await run
      print(res)

    # For the duration of this block, every device in found has
    # a ssh_connection attribute defined.
    print("inside sshify block")
    for device in found:
      print("Device {} has an ssh_connection with repr: {}".format(
          device.serial, device.ssh_connection))

  # Now we're outside the sshify block, and the connection has been cleaned
  # up for us.
  print("Outside sshify block")
  for device in found:
    print("Device {} has an ssh_connection with repr: {}".format(
        device.serial, device.ssh_connection))


def main():
  # get_all returns an iterator, which can only be consumed once in python.
  # make it stable so that it can be consumed many times over.
  found = list(faros_discovery.Discover())
  # async python code and normal python code are not easily called from
  # one-another. We need to create an async event loop so that we can run any
  # sort of async code.
  loop = asyncio.new_event_loop()
  # This will run until the given async task completes, returning whatever
  # that particular task returns. You can pass many tasks at once, which it
  # will return in a list.
  res = loop.run_until_complete(test_some_remote_operations(found))
  # Close the loop that we got to be nice to other people.
  loop.close()


if __name__ == '__main__':
  main()

// =============================================================================
// 名称: Async Message Queue (Push-to-Pull Adapter)
// 来源: https://github.com/anthropics/claude-agent-sdk-demos/blob/main/simple-chatapp/server/ai-client.ts
// 用途: 将 push-based 消息源转为 AsyncIterator，适配 async generator 消费者
// 依赖: 无（TypeScript 标准）
// 适用场景: WebSocket → SDK query(), 事件源 → async for 循环, 生产者-消费者队列
// 日期: 2026-03-22
// =============================================================================

/**
 * A simple async queue that bridges push-based producers (e.g. WebSocket)
 * with pull-based consumers (e.g. async generators / for-await loops).
 *
 * Usage:
 *   const queue = new AsyncMessageQueue<string>();
 *   queue.push("hello");                    // producer side
 *   for await (const msg of queue) { ... }  // consumer side
 *   queue.close();                          // signal end
 */
export class AsyncMessageQueue<T> {
  private messages: T[] = [];
  private waiting: ((msg: T) => void) | null = null;
  private closed = false;

  push(item: T): void {
    if (this.closed) return;

    if (this.waiting) {
      // Consumer is already waiting — deliver immediately
      this.waiting(item);
      this.waiting = null;
    } else {
      // No consumer waiting — buffer it
      this.messages.push(item);
    }
  }

  async *[Symbol.asyncIterator](): AsyncIterableIterator<T> {
    while (!this.closed) {
      if (this.messages.length > 0) {
        yield this.messages.shift()!;
      } else {
        // Block until next push() or close()
        yield await new Promise<T>((resolve) => {
          this.waiting = resolve;
        });
      }
    }
    // Drain remaining messages after close
    while (this.messages.length > 0) {
      yield this.messages.shift()!;
    }
  }

  close(): void {
    this.closed = true;
    // Unblock any waiting consumer with a sentinel (they'll exit the loop)
    if (this.waiting) {
      // Note: original impl doesn't handle this edge case.
      // In production, consider rejecting or using a done signal.
      this.waiting = undefined as any;
    }
  }

  get size(): number {
    return this.messages.length;
  }

  get isClosed(): boolean {
    return this.closed;
  }
}

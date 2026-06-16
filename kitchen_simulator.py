import random
import heapq
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from collections import deque


@dataclass
class Order:
    order_id: int
    arrival_time: float
    prep_start: Optional[float] = None
    prep_end: Optional[float] = None
    cook_start: Optional[float] = None
    cook_end: Optional[float] = None
    pack_start: Optional[float] = None
    pack_end: Optional[float] = None
    is_canceled: bool = False
    cancel_reason: str = ""

    @property
    def total_wait_time(self) -> float:
        if self.is_canceled or self.pack_end is None:
            return 0.0
        return self.pack_end - self.arrival_time

    @property
    def is_completed(self) -> bool:
        return not self.is_canceled and self.pack_end is not None


@dataclass
class Station:
    name: str
    base_time: float
    variance: float
    cancel_threshold: float
    queue: deque = field(default_factory=deque)
    is_busy: bool = False
    current_order: Optional[Order] = None
    current_task_end: float = 0.0

    def process_time(self) -> float:
        delay_factor = random.uniform(1.0 - self.variance, 1.0 + self.variance)
        return max(0.1, self.base_time * delay_factor)


@dataclass
class Event:
    time: float
    event_type: str
    order: Order
    station: Optional[Station] = None

    def __lt__(self, other: 'Event') -> bool:
        return self.time < other.time


class KitchenSimulator:
    def __init__(
        self,
        num_orders: int = 20,
        arrival_interval: Tuple[float, float] = (2.0, 5.0),
        prep_time: float = 4.0,
        cook_time: float = 8.0,
        pack_time: float = 3.0,
        variance: float = 0.4,
        cancel_threshold: float = 30.0,
        seed: Optional[int] = None,
    ):
        if seed is not None:
            random.seed(seed)

        self.num_orders = num_orders
        self.arrival_interval = arrival_interval
        self.cancel_threshold = cancel_threshold

        self.prep_station = Station("备菜", prep_time, variance, cancel_threshold)
        self.cook_station = Station("烹饪", cook_time, variance, cancel_threshold)
        self.pack_station = Station("打包", pack_time, variance, cancel_threshold)

        self.event_queue: List[Event] = []
        self.orders: List[Order] = []
        self.current_time = 0.0
        self.next_order_id = 1

    def schedule_event(self, event: Event):
        heapq.heappush(self.event_queue, event)

    def generate_order_arrivals(self):
        time = 0.0
        for _ in range(self.num_orders):
            order = Order(order_id=self.next_order_id, arrival_time=time)
            self.orders.append(order)
            self.schedule_event(Event(time, "ORDER_ARRIVAL", order))
            interval = random.uniform(*self.arrival_interval)
            time += interval
            self.next_order_id += 1

    def handle_order_arrival(self, event: Event):
        order = event.order
        self.print_event(f"订单 #{order.order_id} 到达", event.time)
        self.prep_station.queue.append(order)
        self.try_start_station_task(self.prep_station, event.time, "PREP")

    def try_start_station_task(self, station: Station, current_time: float, task_type: str):
        if not station.is_busy and station.queue:
            order = station.queue.popleft()

            wait_time = current_time - order.arrival_time
            if wait_time > self.cancel_threshold:
                order.is_canceled = True
                order.cancel_reason = f"在{station.name}前等待超时 ({wait_time:.1f}分钟)"
                self.print_event(f"订单 #{order.order_id} 被取消 - {order.cancel_reason}", current_time)
                self.try_start_station_task(station, current_time, task_type)
                return

            station.is_busy = True
            station.current_order = order
            process_time = station.process_time()
            station.current_task_end = current_time + process_time

            if task_type == "PREP":
                order.prep_start = current_time
                order.prep_end = station.current_task_end
            elif task_type == "COOK":
                order.cook_start = current_time
                order.cook_end = station.current_task_end
            elif task_type == "PACK":
                order.pack_start = current_time
                order.pack_end = station.current_task_end

            delay_info = ""
            base_time = station.base_time
            if abs(process_time - base_time) > base_time * 0.1:
                delay_info = f" {'延迟' if process_time > base_time else '提前'} {abs(process_time - base_time):.1f}分钟"

            self.print_event(
                f"{station.name}开始处理订单 #{order.order_id}"
                f" (预计{process_time:.1f}分钟{delay_info})",
                current_time
            )

            self.schedule_event(Event(station.current_task_end, f"{task_type}_FINISH", order, station))

    def handle_task_finish(self, event: Event):
        station = event.station
        order = event.order
        task_type = event.event_type.replace("_FINISH", "")

        self.print_event(f"{station.name}完成订单 #{order.order_id}", event.time)

        station.is_busy = False
        station.current_order = None

        next_station = None
        next_task = None
        if task_type == "PREP":
            next_station = self.cook_station
            next_task = "COOK"
        elif task_type == "COOK":
            next_station = self.pack_station
            next_task = "PACK"
        elif task_type == "PACK":
            total = order.total_wait_time
            self.print_event(f"✅ 订单 #{order.order_id} 出餐完成！总耗时 {total:.1f} 分钟", event.time)

        if next_station and next_task:
            next_station.queue.append(order)
            self.try_start_station_task(next_station, event.time, next_task)

        self.try_start_station_task(station, event.time, task_type)

    def print_event(self, message: str, time: float):
        print(f"[{time:6.1f}分钟] {message}")

    def run(self):
        print("=" * 70)
        print("🍳 厨房三工位出餐模拟器 开始运行")
        print("=" * 70)
        print(f"配置: {self.num_orders}个订单 | 备菜{self.prep_station.base_time}分钟 "
              f"| 烹饪{self.cook_station.base_time}分钟 | 打包{self.pack_station.base_time}分钟")
        print(f"      波动系数 ±{self.prep_station.variance*100:.0f}% | "
              f"超时取消阈值 {self.cancel_threshold}分钟")
        print("-" * 70)

        self.generate_order_arrivals()

        while self.event_queue:
            event = heapq.heappop(self.event_queue)
            self.current_time = event.time

            if event.event_type == "ORDER_ARRIVAL":
                self.handle_order_arrival(event)
            elif event.event_type.endswith("_FINISH"):
                self.handle_task_finish(event)

        self.print_statistics()

    def print_statistics(self):
        print("\n" + "=" * 70)
        print("📊 模拟结果统计")
        print("=" * 70)

        completed = [o for o in self.orders if o.is_completed]
        canceled = [o for o in self.orders if o.is_canceled]

        print(f"总订单数: {self.num_orders}")
        print(f"✅ 成功出餐: {len(completed)} ({len(completed)/self.num_orders*100:.1f}%)")
        print(f"❌ 被取消: {len(canceled)} ({len(canceled)/self.num_orders*100:.1f}%)")

        if completed:
            wait_times = [o.total_wait_time for o in completed]
            avg_wait = sum(wait_times) / len(wait_times)
            max_wait = max(wait_times)
            slowest_order = max(completed, key=lambda o: o.total_wait_time)

            print(f"\n⏱️  平均等待时间: {avg_wait:.2f} 分钟")
            print(f"🐢 最慢订单: #{slowest_order.order_id}，耗时 {max_wait:.2f} 分钟")

            prep_times = [o.prep_end - o.prep_start for o in completed]
            cook_times = [o.cook_end - o.cook_start for o in completed]
            pack_times = [o.pack_end - o.pack_start for o in completed]

            print(f"\n各工位平均处理时间:")
            print(f"  备菜: {sum(prep_times)/len(prep_times):.2f} 分钟 (基准 {self.prep_station.base_time})")
            print(f"  烹饪: {sum(cook_times)/len(cook_times):.2f} 分钟 (基准 {self.cook_station.base_time})")
            print(f"  打包: {sum(pack_times)/len(pack_times):.2f} 分钟 (基准 {self.pack_station.base_time})")

        if canceled:
            print(f"\n❌ 被取消的订单号: {', '.join(f'#{o.order_id}' for o in canceled)}")
            for o in canceled:
                print(f"   #{o.order_id}: {o.cancel_reason}")

        if completed and canceled:
            print(f"\n📈 出餐效率: {len(completed)}/{self.num_orders} = {len(completed)/self.num_orders*100:.1f}%")

        print("=" * 70)


def main():
    simulator = KitchenSimulator(
        num_orders=15,
        arrival_interval=(2.0, 4.0),
        prep_time=3.0,
        cook_time=6.0,
        pack_time=2.0,
        variance=0.35,
        cancel_threshold=25.0,
        seed=42,
    )
    simulator.run()


if __name__ == "__main__":
    main()

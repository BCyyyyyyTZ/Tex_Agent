def set_nested_value(d, keys, value):
    """
    d: 字典对象
    keys: 路径列表，例如 ["agents", "NexusFlow", "config"]
    value: 要设置的叶子节点值
    """
    for key in keys[:-1]:
        # 如果键不存在，则创建一个空字典并指向它
        d = d.setdefault(key, {})
    # 设置最后一个键的值
    d[keys[-1]] = value
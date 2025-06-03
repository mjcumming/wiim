# LinkPlay Group Management API Reference

> **Purpose**: Document the specific LinkPlay HTTP API commands needed for WiiM group management implementation.

---

## 🎯 **Essential Group Commands**

### **Join Group Command**

```
ConnectMasterAp:JoinGroupMaster:<master_ip>:wifi0.0.0.0
```

- **Purpose**: Makes a device join another device's group as a slave
- **Target**: Send to the slave device's IP
- **Parameters**:
  - `<master_ip>`: IP address of the master device
  - `wifi0.0.0.0`: Fixed suffix for WiFi connection

### **Leave Group Command**

```
multiroom:SlaveKickout:<slave_ip>
```

- **Purpose**: Removes a slave from the group
- **Target**: Send to the master device's IP
- **Parameters**: `<slave_ip>`: IP address of slave to remove

### **Ungroup Command**

```
multiroom:Ungroup
```

- **Purpose**: Disbands the entire group
- **Target**: Send to the master device's IP
- **Use Case**: When master leaves group

---

## 📊 **Group Status Detection**

### **Device Role from getStatusEx**

```json
{
  "group": "0", // Solo or Master
  "group": "1", // Slave
  "master_uuid": "...", // Present when slave
  "uuid": "..." // Device UUID
}
```

### **Master's Slaves from getSlaveList**

```json
{
  "slaves": 2,
  "slave_list": [
    { "uuid": "slave1", "ip": "192.168.1.101", "name": "Kitchen" },
    { "uuid": "slave2", "ip": "192.168.1.102", "name": "Bedroom" }
  ]
}
```

---

## 🏗️ **Implementation Strategy**

### **Group Role Logic**

1. **Slave**: `group == "1"` and has `master_uuid`
2. **Master**: `group == "0"` and `getSlaveList` shows slaves
3. **Solo**: `group == "0"` and no slaves

### **Group Join Process**

1. Master speaker receives join request
2. For each target speaker, send `ConnectMasterAp` to slave IP
3. Update all Speaker objects with new roles
4. Dispatch events to update all entities

### **Group Leave Process**

1. If slave leaving: Send `SlaveKickout` to master
2. If master leaving: Send `Ungroup` to master (disbands group)
3. Update Speaker objects with new roles
4. Dispatch events to update entities

---

This API reference supports our Speaker-centric group management implementation without unnecessary complexity.

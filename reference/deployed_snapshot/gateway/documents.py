DOCUMENTS = {
    "hr-leave": {
        "id": "hr-leave",
        "title": "นโยบายวันลา — ข้อมูลสมมติ",
        "team": "HR",
        "allowed_roles": ["hr_reader"],
        "content": "พนักงานมีวันลาพักร้อน 12 วันต่อปี ต้องแจ้งล่วงหน้า 3 วัน"
    },
    "finance-budget": {
        "id": "finance-budget",
        "title": "งบประมาณฝ่าย Finance — ข้อมูลสมมติ",
        "team": "Finance",
        "allowed_roles": ["finance_reader"],
        "content": "งบโครงการจำลองเดือนตุลาคมคือ 480000 บาท รหัสอ้างอิง FIN-DEMO-482"
    }
}


def can_read(identity, document):
    return (
        identity["team"] == document["team"]
        and identity["role"] in document["allowed_roles"]
    )

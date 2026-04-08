from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User
from app.models.student import StudentProfile, TimetableEntry, ResultEntry, HomeworkEntry, AttendanceRecord, FeeEntry
from app.models.parent import ParentProfile
from app.models.teacher import TeacherProfile, TeacherClass
from app.models.notice import Notice


def seed_demo_data():
    db: Session = SessionLocal()
    try:
        if db.query(User).first():
            return

        pwd = hash_password("123456")

        student_user_1 = User(username="student1", display_name="Aarav Kumar", role="student", password_hash=pwd)
        student_user_2 = User(username="student2", display_name="Diya Kumar", role="student", password_hash=pwd)
        parent_user = User(username="parent1", display_name="Parent Demo", role="parent", password_hash=pwd)
        teacher_user = User(username="teacher1", display_name="Teacher Demo", role="teacher", password_hash=pwd)
        admin_user = User(username="admin1", display_name="Admin Demo", role="admin", password_hash=pwd)
        db.add_all([student_user_1, student_user_2, parent_user, teacher_user, admin_user])
        db.flush()

        student_1 = StudentProfile(user_id=student_user_1.id, class_name="8-A", roll_no=18, guardian_name="Ravi Kumar", phone="+91 9876543210")
        student_2 = StudentProfile(user_id=student_user_2.id, class_name="8-A", roll_no=19, guardian_name="Ravi Kumar", phone="+91 9876543210")
        db.add_all([student_1, student_2])
        db.flush()

        parent_profile = ParentProfile(user_id=parent_user.id)
        parent_profile.children.extend([student_1, student_2])
        db.add(parent_profile)

        teacher_profile = TeacherProfile(user_id=teacher_user.id, department="Mathematics", employee_code="TCH-204")
        db.add(teacher_profile)
        db.flush()

        db.add_all([
            TeacherClass(teacher_profile_id=teacher_profile.id, class_name="8-A", subject="Mathematics", student_count=34),
            TeacherClass(teacher_profile_id=teacher_profile.id, class_name="9-B", subject="Mathematics", student_count=31),
        ])

        db.add_all([
            TimetableEntry(student_profile_id=student_1.id, period="Period 1", subject="Mathematics", time_slot="09:00 - 09:45"),
            TimetableEntry(student_profile_id=student_1.id, period="Period 2", subject="English", time_slot="09:45 - 10:30"),
            TimetableEntry(student_profile_id=student_1.id, period="Period 3", subject="Science", time_slot="10:45 - 11:30"),
            TimetableEntry(student_profile_id=student_1.id, period="Period 4", subject="Social", time_slot="11:30 - 12:15"),
            TimetableEntry(student_profile_id=student_1.id, period="Period 5", subject="Computer", time_slot="01:00 - 01:45"),
        ])

        db.add_all([
            ResultEntry(student_profile_id=student_1.id, subject="Mathematics", marks=86, out_of=100, grade="A"),
            ResultEntry(student_profile_id=student_1.id, subject="English", marks=79, out_of=100, grade="B+"),
            ResultEntry(student_profile_id=student_1.id, subject="Science", marks=91, out_of=100, grade="A+"),
            ResultEntry(student_profile_id=student_1.id, subject="Social", marks=84, out_of=100, grade="A"),
            ResultEntry(student_profile_id=student_1.id, subject="Computer", marks=95, out_of=100, grade="A+"),
        ])

        db.add_all([
            HomeworkEntry(student_profile_id=student_1.id, title="English Essay", description="Write 500 words on Environment", subject="English", due_date="Tomorrow"),
            HomeworkEntry(student_profile_id=student_1.id, title="Math Worksheet", description="Fractions sheet due tomorrow", subject="Mathematics", due_date="Tomorrow"),
            HomeworkEntry(student_profile_id=student_1.id, title="Computer Project", description="Prepare slides on internet safety", subject="Computer", due_date="Friday"),
            HomeworkEntry(student_profile_id=student_2.id, title="Science Diagram", description="Draw plant cell diagram", subject="Science", due_date="Monday"),
        ])

        db.add_all([
            AttendanceRecord(student_profile_id=student_1.id, day_label="Monday", status="Present"),
            AttendanceRecord(student_profile_id=student_1.id, day_label="Tuesday", status="Present"),
            AttendanceRecord(student_profile_id=student_1.id, day_label="Wednesday", status="Absent"),
            AttendanceRecord(student_profile_id=student_2.id, day_label="Wednesday", status="Present"),
        ])

        db.add_all([
            FeeEntry(student_profile_id=student_1.id, title="Tuition Fee", amount=12000, due_date="10 Sep"),
            FeeEntry(student_profile_id=student_1.id, title="Transport Fee", amount=4000, due_date="10 Sep"),
            FeeEntry(student_profile_id=student_1.id, title="Activity Fee", amount=2500, due_date="10 Sep"),
            FeeEntry(student_profile_id=student_2.id, title="Tuition Fee", amount=7000, due_date="10 Sep"),
            FeeEntry(student_profile_id=student_2.id, title="Activity Fee", amount=2000, due_date="10 Sep"),
        ])

        db.add_all([
            Notice(audience="all", title="Holiday Circular", message="School closed on Friday for festival observance."),
            Notice(audience="parent", title="PTM Circular", message="Please attend the PTM with your child report book."),
            Notice(audience="student", title="Sports Practice", message="Football selections on Saturday morning."),
            Notice(audience="teacher", title="Staff Meeting", message="Meeting at 4 PM in the conference room."),
        ])

        db.commit()
    finally:
        db.close()

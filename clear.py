from beirut_pos.services.printer import printer
p = printer._current_printer()
p.open()
p.text("\n" * 20)
p.cut()
p.close()
